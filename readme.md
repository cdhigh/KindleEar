Readme of english version refers to [Readme_EN.md](https://github.com/cdhigh/KindleEar/blob/master/readme_EN.md)

# 简介
这是一个运行在Google App Engine(GAE)上的Kindle个人推送服务应用，生成排版精美的杂志模式mobi/epub格式自动每天推送至您的Kindle或其他邮箱。

此应用目前的主要功能有：  

* 支持类似Calibre的recipe格式的不限量RSS/ATOM或网页内容收集
* 不限量自定义RSS，直接输入RSS/ATOM链接和标题即可自动推送
* 多账号管理，支持多用户和多Kindle
* 生成带图的杂志格式mobi或带图的有目录epub
* 自动每天定时推送
* 内置共享库，可以直接订阅其他网友分享的订阅源，也可以分享自己的订阅源给其他网友
* 强大而且方便的邮件中转服务
* 和Evernote/Pocket/Instapaper等系统的集成

> 注：如果您要求不高，自定义RSS推送功能足以应付一般应用，如果要求排版和完美，可以参照books目录下的文件范本自己添加一个文件再重新上传即可，books目录下的书籍文件都不是随意预置的，每个文件都至少演示一个适用的books编写技巧。
在您懂python的前提下，您可以完全的操控网页，可以生成您需要的最完美的MOBI/EPUB文件。

# 标准部署步骤
1. [申请google账号](https://accounts.google.com/SignUp) 并暂时 [启用不够安全的应用的访问权限](https://www.google.com/settings/security/lesssecureapps) 以便上传程序。  

2. [创建一个Application](https://console.developers.google.com/project)，注意不用申请GCE，那个是60天试用的，而GAE是限额范围内永久免费的。  

3. 安装 [Python 2.7.x](https://www.python.org/downloads/)。  

4. 安装 [GAE SDK](https://cloud.google.com/appengine/downloads)。  

5. 下载 [KindleEar](https://github.com/cdhigh/KindleEar/archive/master.zip) ，解压到一个特定的目录。

6. 在以下三个文件中修改一些参数：  

  文件              |  待修改内容  | 说明                   |  
-------------------|-------------|-----------------------|  
app.yaml           | application | 你的ApplicationId      |  
module-worker.yaml | application | 你的ApplicationId      |  
config.py          | SRC_EMAIL   | 创建GAE工程的GMAIL邮箱   |  
config.py          | DOMAIN      | 你申请的应用的域名        |  

> 如果使用gcloud部署，需要注释掉yaml文件中的application/version项。

7. 转到GAE SDK安装目录(默认为：*C:\Program Files\Google\google_appengine*) 

8. 部署命令：  
8.1 使用appcfg.py：  
	* `c:\python27\python.exe appcfg.py update kindleear目录\app.yaml kindleear目录\module-worker.yaml`  
	* `c:\python27\python.exe appcfg.py update kindleear目录`  

8.2 使用gcloud：  
    * 删除app.yaml和module-worker.yaml开头的两行：application /  version  
    * `gcloud auth login`  
    * `gcloud config set project 你的ApplicationId`  
    * `gcloud app deploy --version=1 KindleEar目录\app.yaml KindleEar目录\module-worker.yaml`  
    * `gcloud app deploy --version=1 KindleEar目录`  
    * [如果服务器没有正常创建数据库索引，可能需要手动执行如下语句]  
      `gcloud datastore indexes create KindleEar目录\index.yaml`  

9. 全部完成后就可以尝试打开域名：  
*http://appid.appspot.com*  (appid是你申请的application名字)  
比如作者的网站域名为：<http://kindleear.appspot.com/>  
**注：初始用户名为 admin，密码为 admin，建议登录后及时修改密码。** 

10. 更详细一点的说明请参照Github上的 [FAQ](http://htmlpreview.github.io/?https://github.com/cdhigh/KindleEar/blob/master/static/faq.html) 或作者网站的 [FAQ](http://kindleear.appspot.com/static/faq.html) 链接。有关部署失败，部署后"internal server error"等问题都有解释。  
**不建议使用GAE Launcher部署KindleEar，除非你知道怎么设置Extra Flags等参数。**

# 简化的部署步骤（推荐）
  假如你不想安装python和GAE SDK，则可以选择如下两种方法之一：  

1. 参考代码库 <https://github.com/bookfere/KindleEar-Uploader> ，里面有详细的教程和服务器脚本，也很简单。  

2. 使用本机脚本：  
2.1 [下载KindleEar](https://github.com/cdhigh/KindleEar/archive/master.zip) 并解压（改目录名为KindleEar）。  
2.2 [下载KindleEar-Uploader](https://drive.google.com/folderview?id=0ByRickMo9V_XNlJITzhYM3JOYW8&usp=sharing) 并解压。  
3.3 将KindleEar目录放到Uploader目录下，双击uploader.bat即开始上传，根据提示输入你的相关信息即可，在第一次成功部署之后，适用uploader再次升级KindleEar则不需要再次输入。  
**此uploader仅适用于Windows系统。**

# 许可协议
KindleEar is licensed under the [AGPLv3](http://www.gnu.org/licenses/agpl-3.0.html) license.  
大体的许可框架是此应用代码你可以任意使用，任意修改，可以商用，但是必须将你修改后的代码开源并保留原始版权声明。

# 主要贡献者
* @rexdf <https://github.com/rexdf> 
* @insert0003 <https://github.com/insert0003> 
* @zhu327 <https://github.com/zhu327> 
* @lord63 <https://github.com/lord63> 
* @th0mass <https://github.com/th0mass> 
* @seff <https://github.com/seff> 
* @miaowm5 <https://github.com/miaowm5> 
* @bookfere <https://github.com/bookfere> 
