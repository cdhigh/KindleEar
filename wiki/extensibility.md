# Recipe 机制与扩展点

## 1. Recipe 三类 ID（贯穿全项目的核心概念）

| 前缀 | 存储位置 | 生成/来源 | 相关代码 |
|---|---|---|---|
| `builtin:<name>` | `application/recipes/builtin_recipes.xml`（元数据索引）+ `builtin_recipes.zip`（源码） | calibre 官方 recipe 打包，**不入数据库** | `lib/recipe_helper.py::GetBuiltinRecipeInfo/GetBuiltinRecipeSource` |
| `custom:<dbId>` | `Recipe` 表（type_='custom'，只存 url/title 等参数，**不存源码**） | 用户在 `/my` 页填 RSS 表单 | 投递时 `GenerateRecipeSource()` 现场生成源码 |
| `upload:<dbId>` | `Recipe` 表（type_='upload'，`src` 存完整 .recipe 源码） | 用户上传 .recipe 文件（先 `compile_recipe` 校验） | `view/subscribe.py` |

URL 中 `:` 转义为 `__`（如 `/tts/custom__12`）。

### GenerateRecipeSource()（lib/recipe_helper.py）
为自定义 RSS 拼一个临时 calibre recipe 子类源码（类名 `UserRecipe+时间戳`），参数来自用户 book_cfg：`oldest_article`、`use_embedded_content`（全文 RSS=True）、`auto_cleanup`（摘要模式=True，走正文提取）、`timefmt/title_fmt`、`language`、`max_articles`（默认 30）、`cover_url`。base 可选 `BasicNewsRecipe` 或 `UrlNewsRecipe`（url2book 用）。

### 内置 recipe 打包/裁剪（tools/）
- `archive_builtin_recipes.py`：把 `*.recipe` 编译合并为 xml+zip，增量式（按 mtime）。
- `trim_recipes.py`：按语言裁剪（`python trim_recipes.py en zh es`）。
- Docker 构建时自动拉 calibre 官方 recipes 更新。

### OPML
导入 `/advanced/import`、导出 `/advanced/export`（view/adv.py，lib/opml.py 解析）。

## 2. 翻译引擎（lib/ebook_translator/）

按 recipe（BookedRecipe.translator JSON）配置，`html_translator.py` 做 HTML 分段翻译并还原排版（双语对照）。

内置引擎（engines/，基类 `base.py`）：
| 类 | 服务 | 备注 |
|---|---|---|
| GoogleFreeTranslate | Google 网页免费接口 | |
| GoogleBasicTranslate | Google API（ADC/Advanced 计费版） | GAE 可用 |
| GeminiPro | Google Gemini | 经 simple_ai_provider |
| ChatgptTranslate | OpenAI 兼容 | |
| AzureChatgptTranslate | Azure OpenAI | |
| DeeplTranslate / Pro / Free | DeepL | |
| YoudaoTranslate | 有道 | |
| BaiduTranslate | 百度 | |
| MicrosoftEdgeTranslate | Edge 免费接口 | 无需 key |
| CustomTranslate | 自定义 API（JSON 模板） | 用户自填 |

**接入新引擎**：在 `engines/` 加类继承 base（实现翻译方法与语言表），在 `engines/__init__.py` 注册；前端配置页模板 `templates/book_translator.html` + `view/translator.py` 路由一般需同步。`/translator/<recipeId>/test` AJAX 可测试。

## 3. TTS 引擎（lib/ebook_tts/）

按 BookedRecipe.tts 配置，`html_audiolator.py` 把章节文本转 mp3 并合并（mp3cat 二进制优先，无则 `pymp3cat.py` 纯 Python）。worker 中音频**先于电子书**推送。

| 引擎 | 服务 | 备注 |
|---|---|---|
| GoogleWebTTSFree | Google 网页免费 | |
| GoogleTextToSpeech | google-cloud-texttospeech | 仅 GAE（依赖 gae 平台库） |
| EdgeTTSFree | edge-tts 库 | 免费 |
| AzureTTS | Azure | |
| ChatGptTTS | OpenAI | |

## 4. AI 摘要（lib/ebook_summarizer/ + lib/simple_ai_provider.py）

- `simple_ai_provider.py` 是统一 AI Chat 适配：google(Gemini)、openai、deepseek、anthropic(Claude)、xai(Grok)、mistral、groq、perplexity、alibaba(通义/dashscope)、atlascloud、cheaperinference、api-route、opper。含模型列表、RPM、上下文长度、多 apiHost/Endpoint。openai/deepseek/xai/atlascloud/cheaperinference/api-route/opper 走 OpenAI 协议，gemini/anthropic 内部转换 payload。
- API Route：在 AI 摘要设置选择 `api-route`，填入自己的 API Key，默认模型 `gpt-6.1-sol`；可通过模型发现选择账户可用模型。默认 16000 token 分段预算和 2 RPM 是保守的客户端设置，并非服务商模型上限或账户配额。接入说明：https://www.api-route.com/en/docs/quickstart 。
- `HtmlSummarizer` 按 token 预算分段摘要；引擎缺省回退 gemini。
- 配置入口 `/summarizer/<recipeId>`（v3.2+ 加入，注意 dbSchemaVersion 迁移）。

## 5. 词典（lib/dictionary/）

在线阅读器查词用（`/reader/dict` + hunspell 词根/拼写建议，依赖 chunspell + marisa-trie + indexed-gzip —— Docker 额外装这三个库的原因）。

9 引擎（`dictionary/__init__.py` 注册）：
- 在线：dict_org（DICT 协议）、dict_cn、dict_cc、merriam_webster、oxford_learners
- 本地文件（放 `DICTIONARY_DIR`）：stardict(.ifo)、mdict(.mdx/.mdd，含 lzo/salsa20/ripemd128 纯 Python 实现)、lingvo(ABBYY DSL)、babylon(.bgl)

## 6. 入站邮件钩子（mail_hook.py 与 MailNewsRecipe）

用户针对**白名单条目**上传的 Python 钩子类文件。钩子统一继承自 `MailNewsRecipe`（位于 `calibre.web.feeds.news`），将邮件预处理与 Calibre Recipe 反反爬、正文清洗完整融为一体。收信时按发件人地址匹配调用。

- **入口/上传**：Advanced → Inbound Mail 页面，每个白名单条目行上有 Hook 按钮 → 对话框上传 .py 文件（AJAX POST `/advanced/inboundmail/hook`，`AdvInboundMailHookPost` 先 `compile_mail_hook()` 校验是否定义了 `MailNewsRecipe` 子类及方法签名，语法错误或高危行为则拦截）。已上传钩子的条目按钮文字变为 Hooked，点击后可在新窗口高亮查看源码（`/advanced/inboundmail/hook/view/<mail>`）。
- **存储**：UserBlob 表，`name='hook:<白名单地址小写>'`，data 为 JSON `{'file': 文件名, 'src': 源码}`。无 schema 迁移；`erase_traces()` 随账号自动清理；删除白名单条目时同步删除钩子（adv.py AdvDel）。
- **匹配**（`match_mail_hook`）：完整地址 > `@域名` > `*`（白名单 `*` 条目可挂全局钩子），大小写不敏感。
- **调用点**：
  1. `run_mail_preprocess_email()`（view/inbound_email.py `ReceiveMailImpl`）— 白名单校验、主题解码之后，存 InBox 之前；
  2. `run_mail_preprocess_soup()`（view/inbound_email.py `ReceiveMailImpl`）— `CreateMailSoup()` 之后，清洗邮件正文并提取 `urls`；
  3. `urls_to_book()`（后台任务 url2book.py）— 若带 `sender`，直接动态继承该发件人的 `MailNewsRecipe` 子类执行电子书转换与外链抓取（享受子类的 `get_browser()`、`keep_only_tags`、`preprocess_html()`）。
- **容错**：钩子执行异常只记 default_log.warning，不影响投递流程；每次收信与转换重新执行（无全局缓存）。
- **测试**：tests/test_inbound_email.py::MailHookTestCase。

钩子代码示例（以继承 `MailNewsRecipe` 为例）：

```python
from calibre.web.feeds.news import MailNewsRecipe

class MyMailHook(MailNewsRecipe):
    merge_mail = True # 是否合订邮件正文为 Chapter 1

    # 阶段 1：原始邮件过滤（可选，返回 None 或修改后的元组）
    def preprocess_email(self, subject, txtBodies, htmlBodies, attachments):
        subject = '[Newsletter] ' + subject
        return subject, txtBodies, htmlBodies, attachments

    # 阶段 2：邮件正文 Soup 清洗（可选，返回清洗后的 soup）
    def preprocess_soup(self, soup, attachments):
        for ad in soup.find_all('div', class_='footer'):
            ad.decompose()
        return soup

    # 阶段 3：外链提取（可选，返回文章 URL 列表）
    def extract_urls(self, soup):
        return [a['href'] for a in soup.find_all('a', href=True) if 'example.com' in a['href']]

    # 阶段 4：反反爬定制与 DOM 清洗（按需覆盖标准 Calibre BasicNewsRecipe 方法）
    def get_browser(self, *args, **kwargs):
        kwargs['user_agent'] = 'CustomApp/1.0'
        br = super().get_browser(*args, **kwargs)
        br.addheaders += [('cookie', 'token=123')]
        return br

    keep_only_tags = [{'class': lambda x: x and 'article-body' in x}]
    remove_tags = [{'class': lambda x: x and 'toolbar' in x}]
```

钩子里可直接使用 `self.log` / `default_log` 记录日志，也可访问 `self.sender`、`self.to`，并支持 import bs4、re 等运行环境已有的库。

## 7. 其他扩展点

| 扩展点 | 位置 | 说明 |
|---|---|---|
| 浏览器扩展正文提取规则 | `/ext/extractor`（view/extension.py） | JSON 规则提取；`/ext/removejs` 去 JS 抓页 |
| 书签脚本 | tools/bookmarklet_src/send_to_kindle.js | 有选区 POST HTML，否则打开 url2book 页 |
| 归档分享 | view/share.py + lib/pocket.py / wallabag.py / webdav_client.py | Evernote/Wiz 走"readability 提取后邮件发送"，Pocket OAuth 在 `/oauth2/<type>` |
| 发信通道 | back_end/send_mail_adpt.py | 新通道需实现 send 分支并加入 `avaliable_sm_services()` |
| 数据库后端 | back_end/db_models_*.py | peewee 系或 weedata 系 |
| 队列后端 | back_end/task_queue_*.py | 实现 3 个 create_xxx_task + init_task_queue_service |
| 正文提取器 | lib/readability（主力）→ lib/justext_extract（改造版 jusText）→ lib/simpleextract（兜底） | 依次回退 |
| calibre 定制参数 | 用户 custom.calibre_options（JSON） | 经 build_ebook.ke_opts 合并 |
| **MCP 工具/资源/提示词** | `application/lib/mcp_tools.py::TOOL_REGISTRY / MCP_RESOURCES / MCP_PROMPTS` | 新增工具 = 加一个 handler 函数 + 注册表条目（name/title/description/inputSchema/handler/readonly），无需改协议层 |

## 8. MCP 服务器（Unreleased）

供支持 MCP 协议的 AI 客户端（Claude、Cursor、Cline 等）以"工具调用"方式操作 KindleEar。典型用法：让 AI 给新闻网站自动编写并反复调试 calibre recipe / 邮件钩子。

### 链路与文件
- 端点 `POST /mcp`（`view/mcp.py`）：`Authorization: Bearer <token>` 鉴权（遍历 `KeUser.custom['mcp_token']` 匹配，token 由设置页"生成 / 重置令牌"按钮管理，存 `user.custom`，**无 schema 迁移**）→ 用户级启用开关 `user.custom['mcp_enabled']`（**默认停用**，在 `/advanced/mcp` 页打勾开启；停用时令牌保留但端点一律 401，替代单独的吊销功能）→ `lib/mcp_protocol.py` 做 JSON-RPC 2.0 分发 → `lib/mcp_tools.py` 执行工具。
- 传输为 Streamable HTTP 的**无状态 JSON 子集**：只实现 POST + application/json 应答，无 SSE/会话/服务端主动请求，零新增依赖（官方 mcp SDK 基于 ASGI，不引入）。
- 只读模式：`user.custom['mcp_readonly']`（设置页勾选）开启后，注册表中 `readonly=False` 的写工具被拒。
- 审计：每次 tools/call 写 `default_log.info('[MCP] user=x calls tool=y')`。

### 能力清单（34 工具 + 4 资源 + 4 提示词）
- 投递/推送：`push_url_to_kindle`（入队）、`push_text_to_kindle`（同步）、`deliver_now`、`list_delivery_logs`、`get_task_status`、`test_delivery`
- 订阅：`list_subscriptions`、`search_builtin_recipes`（1700 内置索引）、`add_custom_rss`、`remove_subscription`、`update_subscription_schedule`、`import_opml`
- 书架（EBOOK_SAVE_DIR 文件系统）：`list_shelf`、`list_articles`、`read_article`、`search_articles`、`delete_book`
- AI 增强：`summarize_article`（复用 ebook_summarizer）、`lookup_word`（复用 dictionary）
- 邮件：`list_inbox`、`read_mail`、`get_sample_email`、`manage_whitelist`
- 系统：`get_service_status`、`get_account_info`
- Recipe 工作台：`fetch_page`（raw/skeleton/text 三格式，skeleton 去文本留 DOM 结构省 token）、`extract_article_preview`（readability→justext→simpleextract 三级对照）、`validate_recipe`、`test_recipe`、`save_recipe`、`get_recipe_source`
- Hook 工作台：`validate_mail_hook`、`test_mail_hook`、`save_mail_hook`
- 资源：`kindlear://subscriptions|shelf|logs/recent|account`；提示词：`create_news_recipe`、`create_mail_hook`、`morning_digest`、`subscription_review`

### recipe/hook 测试执行器（work/recipe_tester.py）
- `run_recipe_test()`：`compile_recipe` → 直接实例化 recipe 类（opts 需 user/verbose/test=(feeds,articles)/lrf/output_profile对象/keep_images，profile 用 `calibre.customize.ui.output_profiles` 按 short_name 解析）→ 实例上设 `delivery_reason='manual'` 绕过 LastDelivered 去重 → daemon 线程执行 + `join(timeout)`（默认 90s、硬上限 300s，`MCP_TOOL_TIMEOUT` 调默认值，结果带 `effective_timeout_seconds`）→ 逐篇读 `feed_N/article_N/index.html`（**不经 fs.read**，fs 路径约定依赖 os.path.join 的绝对路径吞并行为，直接用普通文件路径最稳）→ 汇集 `failed_downloads/aborted_articles` + 捕获 handler 日志。注意 CalibreLogger 在 `_log` 前已把多参数拼成单条 msg，标准 handler 可直接 getMessage()。v2 增强：`max_articles=0` 走 index_only（只 `parse_index`/`parse_feeds` 不下载正文，秒级验证链接筛选）；`include_content=False` 默认只回 `content_chars` 预览（默认 800，控制总输出 ≤32KB）；`download_images` 开关（默认关，`keep_images=False` 会剥除 img 标签，`image_count` 仅在开启时有意义）；失败/中止的文章没有 `orig_url` 属性（仅下载成功回调赋值），读取用 `getattr`；`download()` 中途抛错时 feed_objects/failed_downloads 已赋值，尽量收集部分结果。
- `run_hook_test()`：**绕开会吞异常的 `run_mail_preprocess_*`**，直接 `compile_mail_hook` 拿类后手动实例化执行各阶段；样本取 InBox（body JSON 只存 txtBodies/htmlBodies/附件名，附件内容不可复现，测试时传空表）；`build_book=True` 按 build_ebook 的动态子类模式 + `convert_book(options={'dont_save_webshelf': True})` 干跑（`urls_to_book` 本身只返回字节不发送，天然无推送）。

### 客户端接入
高级设置 → "MCP Server" 页（`/advanced/mcp`）复制端点地址与令牌（页面还提供可直接粘贴的客户端配置示例），在 MCP 客户端配置：
```json
{"mcpServers": {"kindleear": {"url": "http://your-host/mcp",
  "headers": {"Authorization": "Bearer <你的token>"}}}}
```
