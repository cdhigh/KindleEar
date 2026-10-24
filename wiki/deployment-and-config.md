# 配置参考与部署方式

## 1. config.py 全部配置项（均可被同名环境变量覆盖）

`main.py::set_env()` 把 config.py 的值合并进 os.environ，**环境变量优先**。所以 docker-compose/k8s/云平台直接传环境变量即可，不必改文件。

| 配置项 | 默认 | 说明 |
|---|---|---|
| `APP_ID` | 'kindleear' | 应用标识 |
| `APP_DOMAIN` | 空 | 站点域名（自动补 https://） |
| `SERVER_LOCATION` | 'us-central1' | GAE Cloud Tasks 队列区域 |
| `DATABASE_URL` | `sqlite:////data/kindleear.db` | 支持 datastore / sqlite / mysql / postgresql / cockroachdb / mongodb / redis / pickle |
| `TASK_QUEUE_SERVICE` | 'apscheduler' | gae / apscheduler / celery / rq / 空（同步直调） |
| `TASK_QUEUE_BROKER_URL` | 'memory' | redis:// / mongodb:// / sqlite:// / mysql:// / postgresql:// / memory / file://；rq 仅支持 redis |
| `KE_TEMP_DIR` | 空（用内存） | 临时目录（GAE 设 /tmp） |
| `EBOOK_SAVE_DIR` | 空 | 在线阅读电子书目录；**设置后才启用 reader 功能** |
| `DICTIONARY_DIR` | 空 | 离线词典目录 |
| `DOWNLOAD_THREAD_NUM` | 3 | 下载线程数 |
| `ALLOW_SIGNUP` | False | 是否开放注册（配合 AppInfo.signupType/inviteCodes） |
| `SECRET_KEY` | 内置默认 | Flask session 密钥（Docker 入口随机生成） |
| `DELIVERY_KEY` | 内置默认 | 触发投递任务的密钥（/worker、cron） |
| `ADMIN_NAME` | 'admin' | 管理员用户名（首次登录自动建 admin/admin） |
| `POCKET_CONSUMER_KEY` | 空 | Pocket 集成 |
| `HIDE_MAIL_TO_LOCAL` | False | 隐藏 local 发信测试目录 |
| `LOG_LEVEL` | 'INFO' | 日志级别 |
| `DEMO_MODE` | False | 演示模式（登出清库） |

注意：**SMTP 发信配置不在 config.py**，每个用户存 DB（`KeUser.send_mail_service`，可引用管理员配置）。

## 2. 四种部署形态对比

| 维度 | GAE | Docker（推荐自托管） | 裸 VPS | serv00 免费主机 |
|---|---|---|---|---|
| 依赖生成 | `tools/update_req.py gae`（datastore+Cloud Tasks+gTTS 云端库+appengine-python-standard） | `update_req.py docker`（peewee+sqlite+apscheduler+词典三件套；`docker[all]` 装全部可选） | requirements.txt 全量 | serv00_deploy.sh 分批 pip |
| 数据库 | Datastore（weedata） | /data 卷 sqlite（可换） | 任意 peewee 后端 | 需手改 config |
| 定时任务 | Cloud Scheduler（cron.yaml→/deliver） | flask-apscheduler 进程内 | 主机 cron / apscheduler | 主机 cron `python main.py deliver check` |
| 收邮件 | GAE inbound mail（/_ah/mail） | **mailfix 容器**（postfix 25 → POST /mail） | 自建 MX（通常不用） | 不支持 |
| 进程架构 | 双服务：default(F1 自动扩缩) + worker(B2 basic scaling, gunicorn --timeout 1200)；dispatch.yaml 把 /worker、/url2book 分流到 worker | 单容器 gunicorn(1w/3t, :8000) + Caddy(自动 HTTPS)或 nginx | gunicorn(127.0.0.1:8000)+nginx+systemd（tools/nginx/ 模板） | Passenger WSGI |
| 一键脚本 | tools/gae_deploy.sh（云端 Shell：建 app、生成依赖、拉 recipe、启用 13 个 GCP API、部署 5 个 yaml） | docker compose up（或 ke-docker.sh 单容器） | tools/nginx + update_req.py | tools/serv00_deploy.sh |
| 特殊限制 | 不能跑二进制 → mp3 合并用 pymp3cat.py | USE_DOCKER_LOGS 切 stdout 日志；GUNI_CERT/GUNI_KEY 开 HTTPS | certbot 证书（见 tests/readme.developer.md） | 内存小、FreeBSD、需 chunspell whl |

## 3. GAE 五个 yaml 速览

- `app.yaml`：service default，python312（或 python314），`gunicorn -w 2 main:app`，F1（max 2 实例），`app_engine_apis: true`，inbound mail/mail_bounce，env `KE_TEMP_DIR=/tmp`、`DATABASE_URL=datastore`，静态目录 /static /images /recipes，全站 HTTPS。
- `worker.yaml`：service worker，B2 basic_scaling（max 1 实例、idle 20m），`gunicorn --workers 1 --threads 2 --timeout 1200`。
- `dispatch.yaml`：`*/worker*`、`*/url2book*` → worker 服务。
- `cron.yaml`：每小时 `/deliver`；每日 `/removelogs`。
- `queue.yaml`：default 队列 2/min、bucket 5、重试 1 次/5min、退避 60s→600s。

worker.yaml 的实例参数可由 `update_req.py gae[B2,1,t2,20m]` 定制。

## 4. Docker 部署细节

- `Dockerfile` 两阶段：构建阶段拉 calibre 官方 recipes 打包、按 TARGETPLATFORM 选 mp3cat；运行阶段 python:3.14-alpine + 依赖 + 应用，EXPOSE 8000。
- `docker-compose.yml`（Caddy）：kindleear(:8000, volume `./data:/data`) + caddy(80/443) + mailfix(:25)。env：APP_DOMAIN（带 http/https 前缀）、USE_DOCKER_LOGS、TZ。
- `docker-compose-nginx.yml`：同上但 nginx（client_max_body_size 32M，http→https 301）。
- mailfix（docker/postfix/）：alpine+postfix，master.cf 加 myhook 管道把收到的邮件 `curl --data-binary @-` POST 到 `$URL`（默认 http://kindleear:8000/mail）；message_size_limit≈30MB。**它的存在意义 = 替代 GAE inbound mail**。
- CI（.github/workflows/）：手动触发，buildx amd64+arm64，镜像 `kindleear/kindleear:<__Version__>` 和 `:latest`；mailfix 同理 `kindleear/mailfix`。

## 5. 部署形态 × 代码路径关联（排障用）

- 判断当前形态：看 `DATABASE_URL`（datastore=GAE）、有无 `X-Appengine-Cron` 头（GAE cron）、`USE_DOCKER_LOGS`（Docker）。
- GAE 特有行为：`wrap_wsgi_app`（datastore bundled API）、`task_queue_gae.py` Cloud Tasks 回调、gae 发信通道、GoogleTextToSpeech。
- 平台无关：其余全部业务代码。改代码时避免直接 import google.appengine（仅 send_mail_adpt/task_queue_gae/worker.yaml 相关处有条件使用）。
