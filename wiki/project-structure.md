# 项目目录与文件详解

> 路径均相对仓库根。标注 ⚠ 的文件改动需谨慎（涉及双后端兼容或 vendored 代码）。

## 根目录

| 文件 | 作用 |
|---|---|
| `main.py` | 应用入口 + CLI（debug / deliver check / deliver now / log purge）。装配日志、把 config 合并进 os.environ、调用 `init_app()`。`__Version__` 在此定义。 |
| `config.py` | 全部运行配置默认值（DB、队列、域名、注册开关等）。⚠ `tools/update_req.py` 会改写其中的构建日期。详见 deployment-and-config.md。 |
| `app.yaml` `worker.yaml` `cron.yaml` `queue.yaml` `dispatch.yaml` | GAE 部署五件套：主服务 / worker 服务 / 定时任务 / 队列 / URL 分流。 |
| `requirements.txt` | ⚠ 由 `tools/update_req.py` 生成，勿手改。可选项以注释形式存在。 |
| `pyproject.toml` | 仅 pyright 配置（扫描 application/lib，stubPath=typings）。 |
| `database.db` | 本地开发 sqlite 调试库（run_flask.bat 使用），不入生产。 |
| `readme.md` / `readme_zh.md` | 项目介绍、功能列表、部署方式概览。 |
| `.gcloudignore` `.dockerignore` `.gitattributes` `.gitignore` | 构建排除清单。 |
| `.tags` `.tags_sorted_by_file` `.coverage` | 生成物/缓存。 |
| `AGENTS.md` | 工作区指令（Windows/PowerShell 约定）。 |
| `wiki/` | 本知识库。 |

## application/（应用主体）

### 顶层
| 文件 | 作用 |
|---|---|
| `__init__.py` | Flask app 工厂 `init_app()`：Babel、任务队列、DB 钩子、蓝图注册。 |
| `routes.py` | 路由注册中心：定义 bpHome，集中注册 17 个蓝图。 |
| `base_handler.py` | `login_required` / `get_login_user` / `save_delivery_log` 公共设施。 |
| `mail_hook.py` | 入站邮件预处理钩子：用户针对白名单条目上传 python 钩子文件（存 UserBlob，name=`hook:<地址>`），收信时按发件人匹配调用 `hook_email()`（完整签名，暂存收件箱前）/ `hook_email_soup()`（soup 签名，CreateMailSoup 后）。上传时 `compile_mail_hook()` 编译校验（视图层 adv.py 调用）。详见 extensibility.md。 |
| `ke_utils.py` | 通用工具箱：`safe_eval`（执行用户 recipe 沙箱）、类型转换（str_to_int/float/bool）、时间（tz_now/utcnow/time_str）、脱敏（hide_email/hide_website）、`url_validator`、`sanitize_filename`、`xml_escape/unescape`、`compare_version`、`filesizeformat`、`get_directory_size`、`extractHyperLink`、`PasswordManager`（加盐 sha256×1000，兼容旧 md5 迁移）、`ke_encrypt/ke_decrypt`（RC4 风格可逆加密，SMTP 密码等用）。 |

### back_end/（适配层）⚠
| 文件 | 作用 |
|---|---|
| `db_models.py` | 实体定义唯一入口：按 DATABASE_URL 选择 SQL/NoSQL 实现，定义 11 个实体类。⚠ 改字段要同时看两个实现 + dbSchemaVersion 迁移。 |
| `db_models_sql.py` | peewee 实现（sqlite/mysql/pgsql/cockroachdb），含 JSONField、连接管理、建表升级。 |
| `db_models_nosql.py` | weedata ODM 实现（datastore/mongodb/redis/pickle），API 对齐 peewee。 |
| `task_queue_adpt.py` | 队列适配入口：按 TASK_QUEUE_SERVICE `from xxx import *`。 |
| `task_queue_apscheduler.py` | 默认后端：进程内 cron（:40 check_deliver、每日 remove_logs）+ 即时任务。 |
| `task_queue_celery.py` | Celery 后端（beat + worker 需外部进程）。 |
| `task_queue_rq.py` | RQ 后端（仅 redis）。 |
| `task_queue_gae.py` | Google Cloud Tasks 后端（HTTP 回调本站）。 |
| `send_mail_adpt.py` | 发信适配：smtp/webdav/gae/sendgrid/mailjet/local + `send_to_kindle()` + 投递日志。 |

### view/（Web 层，详见 architecture.md 路由表）
| 文件 | 一句话 |
|---|---|
| `admin.py` | 账号管理（增删改、有效期、代配邮件服务）。 |
| `adv.py` | 高级设置大杂烩：现在推送、入站邮件白名单+钩子文件上传（AJAX 编译校验，`/advanced/inboundmail/hook`）、归档分享（Evernote/Wiz/Pocket/Instapaper/wallabag）、OPML 导入导出、封面上传（PIL 缩放 832x1280 存 UserBlob）、自定义 CSS、词典、代理、calibre 参数、`/fwd` 通用转发代理、`/dbimage`、Pocket OAuth。 |
| `deliver.py` | `/deliver` 调度入口：cron 到点判定（书级 send_times 优先于用户级）、`queueOneBook()` 按合并/独立策略建任务。 |
| `extension.py` | 浏览器扩展 API（去 JS 抓页、JSON 规则正文提取）。 |
| `inbound_email.py` | 入站邮件三通道（GAE `/_ah/mail`、postfix `/mail`、mailglove）→ 白名单反垃圾 → 发件人钩子预处理（mail_hook.run_mail_hook）→ 存 InBox → 指令解析（trigger 投递 / convert 附件转 epub / `!links` `!article` `!lang=`）→ 钩子处理 soup（mail_hook.run_mail_content_hook）→ 建 url2book 任务或正文转书；`/webmail/*` 网页收件箱。 |
| `library.py` | 共享订阅库客户端（分享、拉取官方+GitHub 双源去重、报失效）。 |
| `library_offical.py` | 共享库服务端（仅官方站点 kindleear.appspot.com / cdhigh.serv00.net 用）。 |
| `login.py` | 登录/登出/注册/重置密码（token 邮件 24h）；防暴力（失败 sleep 5s）。 |
| `logs.py` | 投递日志页 + `/removelogs` 每日清理（过期用户停推、清收件箱/书架/临时目录、删 30 天前日志）。 |
| `reader.py` | 在线阅读器（书架、`/reader/article/<path>` 静态文章服务、单篇推送、hunspell 查词）。 |
| `settings.py` | 推送设置（kindle 邮箱、delivery_mode=email/local、webshelf_days、时区、send_time/days、书籍格式/设备/语言）+ `get_locale()` i18n。 |
| `share.py` | `/share` 一键归档分发器。 |
| `subscribe.py` | 订阅管理核心：自定义 RSS 增删（AJAX）、上传 recipe（先 compile 校验）、订阅/退订/删除/单书定时、网站账号密码保存、源码查看。 |
| `translator.py` | `/translator/<id>` 双语翻译、`/tts/<id>` TTS、`/summarizer/<id>` AI 摘要：每套 GET 配置页 + POST 保存 + `/test` AJAX 测试；支持 apply_all。 |

### work/（任务执行层）
| 文件 | 作用 |
|---|---|
| `worker.py` | `/worker` 路由 + `WorkerImpl()`：投递总执行器（编译 recipe→分组→构建电子书→TTS 合并→邮件/书架投递）。详见 delivery-pipeline.md。 |
| `url2book.py` | `/url2book` 路由 + `Url2BookImpl()`：URL 列表/文本/邮件内容转电子书推送（download/debug/fetch 三种 action）。 |

### lib/（vendored 库 + 自写工具）⚠ 大部分是第三方代码
**自写/关键粘合层**：
| 文件/包 | 作用 |
|---|---|
| `build_ebook.py` | calibre Plumber 封装：`convert_book()`（recipe/文件→书）、`urls_to_book()`、`html_to_book()`、`ke_opts()`（用户 calibre_options 合并）。 |
| `recipe_helper.py` | `GenerateRecipeSource()` 动态生成自定义 RSS 的 recipe 源码；内置 recipe 读写（XML 索引 + ZIP 源码）。 |
| `urlopener.py` | 核心 HTTP 封装：requests + 超时/重试/表单，模拟 mechanize 浏览器接口（recipe 兼容基石）。 |
| `mechanize.py` | mechanize 兼容垫片（Browser=UrlOpener），老 recipe 零修改运行。 |
| `smtp_mail.py` | 纯 Python SMTP 发信。 |
| `simple_ai_provider.py` | 统一 AI Chat 接口：google/openai/anthropic/xai/mistral/groq/perplexity/alibaba/atlascloud/cheaperinference/opper（含模型列表、RPM、上下文长度）。 |
| `simpleextract.py` | readability 失效时的兜底正文提取。 |
| `html_json_extract.py` | 从页面 script JSON 启发式提取正文（JS 渲染站点）。 |
| `html5_parser.py` | 桩模块：用 html5lib 替代无二进制的 html5-parser。 |
| `html_form.py` | 仿 mechanize 的 HTMLForm。 |
| `image_tools.py` | PIL 图像处理（超长图切分等）。 |
| `filedownload.py` | 文件下载（返回 DownloadedFileTuple）。 |
| `filesystem_dict.py` | 以路径为键的 dict 目录树（内存组织生成物）。 |
| `languages_countries.py` | 语言/国家代码表。 |
| `opml.py` | OPML 解析（导入订阅）。 |
| `pocket.py` | Pocket API OAuth 全流程。 |
| `wallabag.py` | Wallabag API 客户端。 |
| `webdav_client.py` | 极简 WebDAV（PUT/MKCOL/HEAD），存书到网盘。 |
| `requests_file.py` | requests 的 file:// 适配器。 |
| `pymp3cat.py` | 纯 Python mp3 帧级合并（GAE 无二进制环境用）。 |
| `clogging.py` | Calibre 兼容日志器。 |

**增强引擎子包**（详见 extensibility.md）：
- `ebook_translator/` — 双语翻译，10 引擎（Google/Google云/Gemini/ChatGPT/Azure/DeepL/Youdao/百度/Edge免费/自定义）+ `html_translator.py` 分段翻译保排版。
- `ebook_tts/` — TTS 有声书，5 引擎（Google网页免费/Google云/Edge/Azure/ChatGPT）+ `html_audiolator.py`。
- `ebook_summarizer/` — AI 摘要（基于 simple_ai_provider，分段按 token 预算）。
- `dictionary/` — 9 引擎：在线 DICT/dict_cn/dict_cc/merriam_webster/oxford_learners + 本地 stardict/mdict/lingvo/babylon。

**vendored 第三方**（勿随手改）：
- `calibre/` — calibre 精简版（转换管线 plumber/oeb/mobi 读写/metadata/recipes 支持、unihandecode 转音、polish 等）。
- `readability/` — readability-lxml 0.8.1 内嵌（改过 htmls.py shorten_title），主力正文提取。
- `justext_extract/` — 改造版 jusText（CJK 段落判定、保留 img），备用正文提取 + 多语言 stoplists。
- `polyglot/` — calibre 的 Py2/3 兼容垫片。
- `css_selectors/`、`tinycss/` — CSS 选择器引擎与解析器（calibre 依赖）。

### recipes/
| 文件 | 作用 |
|---|---|
| `builtin_recipes.xml` | 全部内置 recipe 的元数据索引（id/title/author/language...，约 1700 个）。 |
| `builtin_recipes.zip` | 内置 recipe 源码包（tools/archive_builtin_recipes.py 生成）。 |
| `shared_rss.json` | GitHub 上的共享 RSS 库快照（library.py 拉取合并）。 |

### templates/、static/、translations/、images/
- `templates/`：Jinja2 模板。布局：base.html（全站）、adv_base.html（高级设置子菜单）。页面与 view 模块一一对应（login/signup/reset/change_password/user_account/admin/home/my/settings/library/logs/webmail/reader/reader_404/word_lookup/book_translator/book_audiolator/book_summarizer + adv_ 系列 + autoback/tipsback 提示页 + debug_cmd 已弃用）。
- `static/`：pure-min.css + base.css/js、webmail.*、reader.*（在线阅读器前端）、library.js、prism.*（recipe 源码高亮）、jquery 3.7、iconfont、favicon。
- `translations/`：Flask-Babel 目录，zh/de/es/fr/it/ja/ko/pt/ru/tr + messages.pot（.po 源在仓库，.mo 编译产物；备份在 tests/pobackup）。
- `images/`：内置封面 cover0-6.jpg、mastheadImage.gif。

## docker/（自托管部署）
| 文件 | 作用 |
|---|---|
| `Dockerfile` | 两阶段构建（python:3.9.19-alpine，多架构）：构建时拉 calibre 官方 recipes 归档、生成 requirements、选 mp3cat。 |
| `Dockerfile-localtest` | 单阶段本地测试镜像。 |
| `run_docker.sh` | 容器入口：随机 SECRET_KEY、TZ，起 gunicorn。 |
| `gunicorn.conf.py` | bind 0.0.0.0:8000，1w/3t，日志 stdout 或 /data 轮转，GUNI_CERT/GUNI_KEY 可开 HTTPS。 |
| `docker-compose.yml` | 推荐三容器：kindleear + caddy(自动 HTTPS) + mailfix(收信)。 |
| `docker-compose-nginx.yml` + `default.conf` | nginx 变体（client_max_body_size 32M）。 |
| `Caddyfile` | Caddy 反代配置。 |
| `ke-docker.sh` / `ubuntu_docker.sh` | 单容器部署/更新脚本；Ubuntu 装 docker 脚本。 |
| `postfix/`（mailfix 镜像） | postfix content-filter 把 25 端口收到的邮件 POST 到 `/mail` —— 替代 GAE inbound mail，让 Docker 版支持邮件推送。 |

## docs/（GitHub Pages 用户文档，Jekyll）
中英双语各一套：intro / deployment / config / extension（浏览器扩展）/ reader / faq / changelog。`docs/images/` 截图。**用户向文档，与 wiki/（开发者向）互补。**

## tests/
- `runtests.py`：unittest 组织器（模块列表、coverage、failfast；`testonly=''` 默认跑全量，可填模块名单测）。
- `test_base.py`：BaseTestCase（建 app/表/test_client/自动登录）。
- `test_login/setting/admin/subscribe/adv/logs/inbound_email/share(排除)/library_offical.py`：对应 view 模块的功能测试。
- `tools/`：`run_datastore_emulator.bat`、`test_datastore.py`、`test_nosql.py`（datastorm 模拟器验证）、`test_calibre2.py`（本地生成 epub/mobi 样书）。
- `rss/`：测试 fixture（rss.xml、local_file_rss.recipe 等）。`debug_mail/`：调试样本。`pobackup/`：po 备份。`readme.developer.md`：开发者备忘（电子书生成调用链、i18n 三步、证书、平台额度对比）。

## tools/（构建/部署/维护）
| 文件 | 作用 |
|---|---|
| `update_req.py` | **核心**：按目标（docker/docker[all]/gae/gae[B2,1,t2,20m]）生成 requirements.txt 并改写 config.py/main.py 构建日期。内含 DB/队列/平台依赖矩阵。 |
| `archive_builtin_recipes.py` | 把 *.recipe 编译打包为 builtin_recipes.xml+zip（增量）。 |
| `trim_recipes.py` | 按语言裁剪内置 recipe 库。 |
| `gae_deploy.sh` | GAE 一键部署（含启用 13 个 GCP API、recipe 更新）。 |
| `serv00_deploy.sh` | serv00 免费主机部署（分批 pip、FreeBSD chunspell whl、passenger_wsgi.py）。 |
| `run_flask.bat` / `start_celery.bat` | Windows 本地调试启动 / celery worker。 |
| `pybabel_extract.bat` `pybabel_compile.bat` `pybabel_commands.txt` `babel.cfg` | i18n 提取/编译工作流。 |
| `pybabel_auto_translate.py` | 以中文 po 为参照调用外部 autopo AI 翻译其他语言（作者私用）。 |
| `bookmarklet_src/send_to_kindle.js` | "Send to Kindle" 书签脚本源码。 |
| `mp3cat/` | mp3 合并二进制（amd64/arm64/win）+ readme。 |
| `nginx/` | 裸 VPS：gunicorn.conf.py、systemd unit、logrotate、nginx 站点配置。 |

## 其他
| 路径 | 作用 |
|---|---|
| `.github/workflows/docker_build_push.yaml` | 手动触发：多架构构建推送 kindleear/kindleear 镜像（tag 取自 main.py `__Version__`）。 |
| `.github/workflows/mailfix_build_push.yaml` | 手动触发：构建推送 kindleear/mailfix。 |
| `typings/__builtins__.pyi` | pyright 存根：声明 builtins 注入的 appDir/appVer/default_log。 |
