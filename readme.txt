Readme of english version refers to Readme_EN.txt

一、这是一个运行在Google App Engine(GAE)上的Kindle个人推送服务器，生成排版精美的杂志模式MOBI格式自动每天推送至您的kindle，
    此网站应用目前的功能有：
    1.支持类似calibre的recipe格式的自定义RSS收集，需要写代码，需要有一点点python基础
    2.自定义RSS，不需要python基础，直接输入RSS链接和标题即可自动推送
    3.多账号管理，也就是支持多kindle
    4.带图的杂志格式MOBI
    5.自动每天定时推送

    注：如果您要求不高，自定义RSS推送功能能应付一般应用，如果要求排版和完美，可以参照books目录下的文件自己增加一个文件，
    在您懂python的前提下，您可以完全的操控网页，可以生成您需要的最完美的MOBI文件。

二、部署步骤：
    1.申请GAE账号并创建一个application。https://appengine.google.com/
    2.下载GAE SDK。https://developers.google.com/appengine/downloads?hl=zh-CN
    3.安装Python 2.7 如果已经安装了，跳过此步骤
    4.下载本应用的所有文件，放到一个特定的目录。
    5.修改app.yaml的第一行：将kindleear修改为你申请的application名字
    6.修改config.py中的这几个变量
      SrcEmail ：你申请GAE账号时的GMAIL邮箱
      TIMEZONE ：默认时区
    7.转到GAE SDK安装目录（默认为：C:\Program Files\Google\google_appengine）
      执行CMD命令：c:\python27\python.exe appcfg.py update kindleear目录
      比如：c:\python27\python.exe appcfg.py update c:\kindleear
      依次输入邮箱和密码，等结束后就可以打开域名：
      app_name.appspot.com (app_name是你申请的application名字)
      比如作者的网站域名为：kindleear.appspot.com
      开始您的个人推送服务了。
      注：初始用户为admin，密码为admin，建议登陆后及时修改密码。
    8.更详细一点的说明请参照FAQ。

三、许可

KindleEar is Licensed under the GPL license: http://www.gnu.org/licenses/gpl.html