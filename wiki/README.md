# KindleEar Wiki（LLM 导航索引）

> 本目录是为 LLM / 新开发者准备的**项目知识库**。目标是：读这几篇文档即可建立对整个工程的准确认知，避免每次重新扫描全部源码，节省 token。
> 最后更新基于代码版本 **v3.5.3**（2026-10 核对）。如果代码大版本变化，请先核对 `main.py` 的 `__Version__` 再信任本文档。

## 项目一句话

KindleEar：可自托管的 Kindle 个人推送服务（Python/Flask）。聚合 RSS/ATOM/JSON/网页（兼容 calibre recipe 格式，内置约 1700 个 recipe），按订阅时间表定时生成 epub/mobi（可选 TTS mp3、双语翻译、AI 摘要）并通过邮件/WebDAV/本地书架投递到 Kindle；同时内置墨水屏友好的在线阅读器。

## 文档地图

| 文档 | 内容 | 什么时候读 |
|---|---|---|
| [architecture.md](architecture.md) | 启动流程、Flask 装配、蓝图路由表、四大适配层（DB/任务队列/邮件/日志） | 改动任何后端逻辑前 |
| [project-structure.md](project-structure.md) | 全目录树 + 每个文件/模块的职责一句话 | 找"某功能在哪个文件"时 |
| [data-models.md](data-models.md) | 全部数据库实体、字段、SQL/NoSQL 双后端切换、schema 升级机制 | 改数据结构、查字段含义 |
| [delivery-pipeline.md](delivery-pipeline.md) | 核心投递流水线：cron→/deliver→队列→WorkerImpl→构建→发送；url2book 与入站邮件流程 | 调试"为什么没推送到"类问题 |
| [extensibility.md](extensibility.md) | recipe 三类 ID 机制、翻译/TTS/AI 摘要/词典引擎清单与接入方式、内置 recipe 打包 | 加引擎、加 recipe、改扩展功能 |
| [deployment-and-config.md](deployment-and-config.md) | config.py 全部配置项、环境变量覆盖、GAE/Docker/VPS/serv00 四种部署差异 | 部署、改配置 |
| [dev-guide.md](dev-guide.md) | 本地运行（Windows）、测试、i18n 工作流、tools 脚本、开发者注意事项 | 开发调试前 |

## 最小事实集（速记卡）

- **入口**：`main.py` → `init_app()`（`application/__init__.py`）。WSGI 对象 `app`；celery 模式另有 `celery_app`。`python main.py debug` 起 Flask 开发服务器；`python main.py deliver check|now`、`log purge` 是 CLI 子命令（供无队列主机 crontab 用）。
- **框架**：Flask 3 + Flask-Babel，**17 个 Blueprint** 在 `application/routes.py::register_routes()` 集中注册，无自动路由扫描。
- **数据库**：`DATABASE_URL` 一项配置切换 8 种后端（datastore/mongodb/redis/pickle 走自写 weedata ODM；sqlite/mysql/postgresql/cockroachdb 走 peewee）。实体类统一定义在 `application/back_end/db_models.py`。
- **任务队列**：`TASK_QUEUE_SERVICE` 切换 gae(Cloud Tasks)/apscheduler(默认,进程内)/celery/rq/空(同步直调)。适配层在 `application/back_end/task_queue_adpt.py`，对外只有 3 个创建任务函数。
- **发信**：`application/back_end/send_mail_adpt.py`，6 通道（smtp/webdav/gae/sendgrid/mailjet/local），按每个用户的 `KeUser.send_mail_service` JSON 字段分发（不在 config.py）。
- **电子书生成**：`application/lib/build_ebook.py` 封装 calibre 的 `Plumber`（vendored 在 `application/lib/calibre/`，大量精简）。`application/lib/` 下全部是内置第三方库（readability、feedparser 配套、词典解析等），**不要把 lib/ 当作项目自有业务代码**。
- **三类 recipe ID**：`builtin:<name>`（打包在 `application/recipes/builtin_recipes.xml|zip`，不入库）、`custom:<dbId>`（自定义 RSS，投递时动态生成源码）、`upload:<dbId>`（上传的 .recipe 源码存 DB）。
- **用户配置存放**：`KeUser` 的 JSON 字段 `base_config` / `book_config` / `custom`，读写用 `user.cfg('x')` / `user.book_cfg('x')` / `user.set_cfg()`。
- **builtins 注入**：`appDir`、`appVer`、`default_log`、`_`（gettext）由 main.py 注入，类型存根在 `typings/__builtins__.pyi`。
- **部署四形态**：GAE（双服务 default+worker，datastore+Cloud Tasks）、Docker（单容器+Caddy/nginx+可选 mailfix 收信容器）、裸 VPS（gunicorn+nginx，tools/nginx）、serv00 免费主机。详见 deployment-and-config.md。

## 高频问题快速定位

| 问题/需求 | 先看 |
|---|---|
| "推送没有执行" | delivery-pipeline.md（触发链路）+ config.py 的 TASK_QUEUE_SERVICE |
| "某页面 404 / 找路由" | architecture.md 蓝图路由表 |
| "改数据库字段" | data-models.md（注意 SQL/NoSQL 双实现 + dbSchemaVersion 升级） |
| "加一个翻译/TTS/词典引擎" | extensibility.md 对应小节 |
| "内置 recipe 太大/更新" | extensibility.md + tools/archive_builtin_recipes.py、trim_recipes.py |
| "本地跑不起来" | dev-guide.md（Windows：tools/run_flask.bat 的环境变量组合） |
