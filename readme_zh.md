[English](readme.md) · __简体中文__

---

**[项目文档](https://cdhigh.github.io/KindleEar)**    


[体验站点1](https://kindleear.koyeb.app/)  
[体验站点2](https://kindleear.onrender.com/)    
注：体验站点是在koyeb/render上搭建的免费服务，render第一次打开会大约有50s的启动时间，登录账号密码为 `admin/admin`，一段时间不活动后所有数据会被自动清除，所以可以大胆放心的进行任何操作，你可以进行电子书推送测试。  



2024-06-01  **KindleEar 3.1 版本发布，新增一个为墨水屏特别优化的在线阅读器(仅Docker版本)**     

**主要新特性:**
* 全面支持Python 3   
* 全新设计的软件架构   
* 跨平台支持，告别对 GAE 平台的依赖   
* 支持邮件推送和在线阅读(仅Docker版本)，内置专门为电子墨水屏优化的在线阅读器     
* 支持 Calibre 的 recipe 格式，无需修改    
* 内置一千多个 Calibre recipe 文件    
* 内置双语对照翻译功能，突破语言壁垒，轻松获取信息和学习外语    
* 内置文本转语音功能，将每日新闻转化为声音，让您无需阅读，也能轻松获取信息     
* 包含浏览器扩展程序，无需编码即可制作爬虫脚本，便捷推送任意网站（虚假宣传）      



# 简介
这是一个Kindle个人推送服务应用，可以将其部署在各种支持Python的托管平台或VPS上。   
每天自动聚合各种网络信息制作成epub/mobi/mp3格式推送至您的Kindle或其他电子书阅读器。    
同时支持在线阅读，包含一个为墨水屏专门优化的在线阅读器。    


此应用目前的主要功能有：  

* 支持Calibre的recipe格式的不限量RSS/ATOM/JSON或网页内容收集
* 不限量自定义RSS，直接输入RSS/ATOM/JSON链接和标题即可自动推送
* 多账号管理，支持多用户和多Kindle
* 生成带图像有目录的epub/mobi
* 自动每天定时推送或在线阅读
* 内置共享库，可以直接订阅其他网友分享的订阅源，也可以分享自己的订阅源给其他网友
* 强大而且方便的邮件中转服务
* 和Evernote/Pocket/Instapaper/wallabag等系统的集成





![Screenshot](https://raw.githubusercontent.com/cdhigh/KindleEar/master/docs/images/scrshot.gif)






# 许可协议
KindleEar is licensed under the MIT License.  
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

<a href="https://www.buymeacoffee.com/cdhigh" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>
