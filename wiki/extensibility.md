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

- `simple_ai_provider.py` 是统一 AI Chat 适配：google(Gemini)、openai、anthropic(Claude)、xai(Grok)、mistral、groq、perplexity、alibaba(通义/dashscope)、atlascloud、cheaperinference。含模型列表、RPM、上下文长度、多 apiHost。openai/xai/atlascloud/cheaperinference 走 OpenAI 协议，gemini/anthropic 内部转换 payload。
- `HtmlSummarizer` 按 token 预算分段摘要；引擎缺省回退 gemini。
- 配置入口 `/summarizer/<recipeId>`（v3.2+ 加入，注意 dbSchemaVersion 迁移）。

## 5. 词典（lib/dictionary/）

在线阅读器查词用（`/reader/dict` + hunspell 词根/拼写建议，依赖 chunspell + marisa-trie + indexed-gzip —— Docker 额外装这三个库的原因）。

9 引擎（`dictionary/__init__.py` 注册）：
- 在线：dict_org（DICT 协议）、dict_cn、dict_cc、merriam_webster、oxford_learners
- 本地文件（放 `DICTIONARY_DIR`）：stardict(.ifo)、mdict(.mdx/.mdd，含 lzo/salsa20/ripemd128 纯 Python 实现)、lingvo(ABBYY DSL)、babylon(.bgl)

## 6. 入站邮件钩子（mail_hook.py）

用户针对**白名单条目**上传的 python 预处理钩子（类似 recipe 的用户可编程扩展点），收信时按发件人地址匹配调用。

- **入口/上传**：Advanced → Inbound Mail 页面，每个白名单条目行上有 Hook 按钮 → 对话框上传 .py 文件（AJAX POST `/advanced/inboundmail/hook`，`AdvInboundMailHookPost` 先 `compile_mail_hook()` 编译+执行校验，无 `hook_*` 函数/语法错误/签名不符则报错不入库）。已上传钩子的条目按钮文字变为 Hooked，点击后的对话框里有 View 按钮，在新窗口查看钩子源码（`/advanced/inboundmail/hook/view/<mail>`，与查看 recipe 源码相同的 prism 高亮展示）。
- **存储**：UserBlob 表，`name='hook:<白名单地址小写>'`，data 为 JSON `{'file': 文件名, 'src': 源码}`。无 schema 迁移；`erase_traces()` 随账号自动清理；删除白名单条目时同步删除钩子（adv.py AdvDel）。
- **匹配**（`match_mail_hook`）：完整地址 > `@域名` > `*`（白名单 `*` 条目可挂全局钩子），大小写不敏感。
- **调用点**（view/inbound_email.py `ReceiveMailImpl`）：
  1. `run_mail_hook()` — 白名单校验、主题解码之后，存 InBox 之前；
  2. `run_mail_content_hook()` — `CreateMailSoup()` 之后。
- **容错**：钩子执行异常只记 default_log.warning，不影响投递流程；每次收信重新 exec（无缓存）。
- **测试**：tests/test_inbound_email.py::MailHookTestCase。

钩子文件为普通 python 文件，至少定义以下两个函数之一（可原地修改参数，也可返回新值元组）：

```python
def hook_email(sender, to, subject, txtBodies, htmlBodies, attachments):
    #参数与 ReceiveMailImpl() 一致，在解析邮件之前调用
    #sender: str；to: str 或 list（通道而异）；subject: str；txtBodies/htmlBodies: [str]；attachments: [(fileName, bytes)]
    return subject, txtBodies, htmlBodies, attachments  #或返回 None

def hook_email_soup(sender, to, soup, attachments):
    #soup 为 BeautifulSoup 实例，在邮件正文转 soup 后调用
    tag = soup.new_tag('p')
    tag.string = 'appended by hook'
    soup.body.append(tag)
    return soup, attachments  #或返回 None
```

钩子里可直接使用 `default_log` 记录日志，也可 import bs4 等运行环境已有的库。

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
