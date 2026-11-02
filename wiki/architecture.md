# 架构总览

KindleEar v3 是 **Flask 单体应用**（v2 及以前是 GAE webapp，v3 起纯 Flask，可跑在任何 WSGI 主机上）。分层方式是"**Web 层 → 适配层 → 任务执行层**"，三个外部依赖（数据库、任务队列、邮件服务）都通过**适配层**隔离，靠配置切换实现。

## 1. 启动流程

```
main.py
 ├─ 安装 CalibreLogger（lib/clogging.py），注入 builtins: default_log / appDir / appVer
 ├─ set_env(): config.py 的配置合并进 os.environ（环境变量优先，可覆盖 config.py 默认值）
 ├─ init_app()  (application/__init__.py)
 │   ├─ 创建 Flask 实例（模板 application/templates，静态 application/static，MAX_CONTENT_LENGTH=32MB）
 │   ├─ Flask-Babel i18n（translations 目录，locale_selector=view/settings.get_locale，注入 builtins: _）
 │   ├─ init_task_queue_service(app)   ← 任务队列适配层
 │   ├─ create_database_tables()       ← 仅 SQL 后端执行建表/升级
 │   ├─ 全局钩子：before_request（永久 session/g.version/g.now/connect_database）
 │   │             teardown_request（close_database）
 │   └─ routes.register_routes(app)   ← 集中注册 18 个 Blueprint
 └─ 若 DATABASE_URL == 'datastore'：wrap_wsgi_app 包装 wsgi_app 启用 GAE bundled API
```

导出对象：`app`（gunicorn main:app）、`main.py celery_app`（celery 模式）。

`main.py` 还兼任 CLI：`python main.py debug`（开发服务器）、`deliver check`（检查到点用户并触发投递）、`deliver now`（全量投递）、`log purge`（清理 30 天前日志）。后三者供无队列/无常驻进程的主机用外部 crontab 调用。

## 2. 蓝图与路由（application/routes.py）

无自动扫描，全部手工注册。URL→视图映射在各自 view 模块内的 `@bp.route` 装饰器上。

| Blueprint | 模块 (application/view/) | 前缀/典型路由 | 职责 |
|---|---|---|---|
| bpHome | (routes.py 自身) | `/`、`/images/<f>`、`/recipes/<f>` | 主页与静态资源 |
| bpLogin | login.py | `/login` `/logout` `/signup` `/resetpwd` | 登录注册（首次启动自动建 admin/admin） |
| bpAdmin | admin.py | `/admin` `/account/*` | 账号管理 |
| bpAdv | adv.py | `/advanced/*` `/fwd` `/oauth2*` `/dbimage` | 高级设置：立即推送、白名单、归档分享、OPML、封面/CSS、词典、代理、calibre 参数、通用转发代理、Pocket OAuth |
| bpDeliver | deliver.py | `/deliver` | 投递调度入口（cron 回调 + 手动推送） |
| bpSubscribe | subscribe.py | `/my` `/recipe/<act>` `/customrss/<act>` `/viewsrc` `/notifynewsubs` | 订阅管理核心 |
| bpSettings | settings.py | `/settings` `/env` `/setlocale` `/send_test_email` | 推送/书籍/邮件设置 + i18n locale |
| bpLibrary | library.py | `/library/*` | 共享订阅库客户端（分享/拉取/报失效） |
| bpLibraryOffical | library_offical.py | `/kelibrary/*` `/translib` `/exportlib` | 共享库服务端（仅官方站点用） |
| bpLogs | logs.py | `/logs` `/removelogs` | 投递日志 + 每日清理 |
| bpReader | reader.py | `/reader/*` | 在线阅读器（书架/文章静态/推送/查词） |
| bpExtension | extension.py | `/ext/removejs` `/ext/extractor` | 浏览器扩展 API（share key 鉴权） |
| bpShare | share.py | `/share` | 一键归档 Evernote/Wiz/Pocket/Instapaper/wallabag |
| bpTranslator | translator.py | `/translator/<id>` `/tts/<id>` `/summarizer/<id>` | 翻译/TTS/AI 摘要配置与测试 |
| bpWorker | work/worker.py | `/worker` `/notifynewsubs` | **任务队列回调**：执行投递 |
| (url2book) | work/url2book.py | `/url2book` | URL/文本转书任务回调（worker 服务/队列） |
| bpInBoundEmail | inbound_email.py | `/_ah/bounce` `/_ah/mail/<p>` `/mail` `/mailglove` `/webmail/*` | 入站邮件（GAE/postfix/mailglove）+ 网页收件箱 |
| bpMcp | mcp.py | `/mcp` `/mcp/token` `/advanced/mcp` | MCP（Model Context Protocol）服务器端点 + 设置页：Bearer token 鉴权 + JSON-RPC 分发（协议在 lib/mcp_protocol.py，工具注册表在 lib/mcp_tools.py） |

注意：`/worker`、`/url2book` 在 GAE 上由 dispatch.yaml 路由到独立 **worker 服务**；在 Docker/单机部署中是同进程普通路由。

## 3. 四个适配层（application/back_end/ + lib/clogging.py）

### 3.1 数据库适配（db_models.py）
- 入口 `db_models.py` 按 `DATABASE_URL` 前缀 `from db_models_sql import *` 或 `from db_models_nosql import *`，再定义**与后端无关的实体类**。
- SQL 实现：peewee（sqlite/mysql/postgresql/cockroachdb），自定义 JSONField；`create_database_tables()` 负责：按 `AppInfo.dbSchemaVersion` 建表和迁移升级。
- NoSQL 实现：作者自写 **weedata** ODM（peewee 兼容 API），支持 datastore/mongodb/redis/pickle。`connect/close_database` 为空操作。
- 实体清单见 [data-models.md](data-models.md)。

### 3.2 任务队列适配（task_queue_adpt.py）
按环境变量 `TASK_QUEUE_SERVICE` 导入对应后端（`from task_queue_xxx import *`），对外统一 3 个函数 + 初始化：

| 函数 | 用途 | 回调/执行 |
|---|---|---|
| `create_delivery_task(payload)` | 单用户投递 | POST→`/worker` (GET 回调) |
| `create_url2book_task(payload)` | URL/邮件内容转书 | `/url2book`（GAE 必须 POST） |
| `create_notifynewsubs_task(payload)` | 新订阅通知官方库 | `/notifynewsubs` |

| 后端 | 定时触发 | 说明 |
|---|---|---|
| `gae` | cron.yaml `/deliver` | Google Cloud Tasks，队列名 `default`，HTTP 回调本站 |
| `apscheduler`（默认） | 进程内 cron：每小时 :40 check_deliver、每日 remove_logs | flask-apscheduler BackgroundScheduler；jobstore 按 `TASK_QUEUE_BROKER_URL` 选 memory/redis/mongodb/sqlalchemy |
| `celery` | beat：每小时 :50 check_deliver、每月 1 日 remove_logs | 需外部 `celery -A main.celery_app worker/beat` |
| `rq` | `.cron()` 注册 | 仅 redis broker，需 `flask rq worker` |
| 空字符串 | 无 | 同步直调（测试/CLI 用），`main.py deliver check` 即此路径 |

定时与执行分两层：**定时层**（cron/beat）只调 `MultiUserDelivery` 判断哪些用户到点 → `create_delivery_task` 入队；**执行层**（`/worker`）才真正抓取、生成、发送。

### 3.3 邮件适配（send_mail_adpt.py)
统一入口 `send_mail(user, to, subject, body, attachments, ...)`，按用户 `send_mail_service.service` 分发 6 通道：`smtp`（lib/smtp_mail.py）/ `webdav`（不发信，上传网盘）/ `gae` / `sendgrid` / `mailjet` / `local`（存本地目录调试）。高层封装 `send_to_kindle()`（自动附件命名 + 写 DeliverLog）与 `send_html_mail()`。`avaliable_sm_services()` 按已装依赖动态返回可用通道。

### 3.4 日志（lib/clogging.py）
`CalibreLogger` 兼容 calibre 的多参数/可调用/0-3 级 filter_level 日志风格；`set_log_level()` 统一 root/gunicorn/calibre 三 logger 的级别与格式（GAE 上省略时间戳）。

## 4. 请求处理公共设施（application/base_handler.py）

- `login_required(forAjax=False)` 装饰器：未登录重定向登录页（Ajax→`/needloginforajax`），并把 `KeUser` 实例以 `user` 关键字参数注入视图函数。
- `get_login_user()`：从 session（`login==1 && userName`）取当前用户。
- `save_delivery_log()`：写 DeliverLog 投递记录。

## 5. 目录分层心智模型

```
application/
  view/      ← Web 层（页面 + AJAX + GAE 回调）
  work/      ← 任务执行层（worker.py 投递, url2book.py 网页转书）
  lib/       ← vendored 第三方库（calibre 精简版、readability、词典、翻译/TTS/摘要引擎）+ 自写工具
  back_end/  ← 适配层（DB、队列、邮件）
  templates/ static/ translations/ recipes/  ← 表现层资源
```

改业务逻辑通常在 `view/` 与 `work/`；改通用行为在 `back_end/`；`lib/calibre` 尽量不动（升级 calibre 版本时才整体替换）。
