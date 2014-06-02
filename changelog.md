#Changelog for KindleEar

##1.20.3
  1. 修改内置书籍TED渤海湾以适应其网站改版。

##1.20.3
  1. fix book 'TEDxBohaiBay'.

##1.20.2
  1. 针对使用图片延迟加载技术的网页特殊处理，可以获取部分此类网页的图片。

##1.20.2
  1. Supports some webpage which images take a 'data-src' attribute to load asynchronous content.
  
##1.20.1
  1. 新特性，在合并推送时将各书籍的封面拼贴起来。默认已经开启，如果你使用以前的config.py，请设置DEFAULT_COVER_BV=None，如果不喜欢此效果，可以设置DEFAULT_COVER_BV='cv_bound.jpg'
  2. bugfix: 修正保存到evernote不成功的问题（1.13引入）
  
##1.20.1
  1. Paste all covers into one when merge books into one. DEFAULT_COVER_BV=None (default value) to enable the feature.
  2. bugfix: send mail to evernote failed. (bug from version 1.13)
  
##1.20
  1. 增加一个简单的正文提取模块，在readability失败后启用。
  2. 增强的网页解码器，综合考虑http响应头/html文件头/chardet检测结果，效率更高，乱码更少。
  3. 支持需要登陆才能查看文章的网站，请参照FAQ如何使用。
  4. 针对一天推送多次的需求，书籍属性‘oldest_article’大于365则使用*秒*为单位。
  5. 增强的密码安全，加salt然后md5，无法通过密码词典破解，在可接受的代价范围内无法暴力破解。
    （仅新账号启用，如果需要可以删掉admin然后重新登陆就会新建admin账号）
  6. 整理文件夹结构，将相关库都放到lib目录下。
  7. 其他一些小的可用性增强。
  > 升级注意:书籍的fetcharticle()增加了一个参数，如果你定制的书籍使用到此接口，需要修改。
  
##1.20
  1. a new simple algorithm to extract content of webpage when module readability failed.
  2. a new enhanced decoder for webpage which detection algorithm includes more parameters:
    http response header, meta of html, result of chardet.
  3. support site that need subscription, refers to FAQ for more detail.
  4. use *second* as unit when value of property 'oldest_article' of book more than 365.
  5. Enhanced password encryption with salt, more safe when face a brute force attack.
    (for new account only, you can delete account admin and login again for enjoy it.)
  6. neaten folder structure, put all libs into folder 'lib'.
  7. some minor improves for usability.
  > Note:interface fetcharticle() in base.py modified (a new parameter added), if your book implemented it, please modify it to work.
