---
sort: 6
---
# FAQ


## 何为全文RSS？
全文RSS是我给这一类RSS的称呼，也不知道正确的名字是什么，在Calibre里面叫 Embedded Content。
这一类RSS在其XML文件中已经给出了文章的全文内容，只需要进行一次连接，即可获得很多篇文章的全文内容，而不需要像普通的RSS一样，每一篇文章都需要连接网络抓取其文章内容，大大节省了时间和其他资源消耗。   
如何确认自己要订阅的RSS是否是全文RSS？很简单，使用浏览器打开RSS对应的链接，查看是否已经有全部的文章内容，如果是，则为全文RSS。如果仅给出文章摘要，则不是。  


## 全文RSS能否按照摘要RSS处理？反之是否可以？
全文RSS当然可以按照摘要RSS处理，这样就忽略RSS链接中给出的文章内容，而直接到原链接中获取，只是多耗费一些时间，导致支持的RSS数量下降。如果是摘要RSS，则不能按全文RSS处理，否则会导致文章内容不全。


## 如何给某个Recipe自定义推送时间？
除了在设置页面设置一个统一的推送日和时间外，每个Recipe都可以自定义一个自己唯一的推送日和推送时间，一旦设置，则统一的推送时间设置将对此Recipe无效。方法是在“我的订阅”的“已订阅”区段，点击某个Recipe后边的圆形按钮，使用弹出的“自定义推送时间”按钮进行设置，可以设置为仅某一天或几天推送，也可以设定一天推送多次。
不过自定义推送时间仅针对内置和上传的Recipe，自定义RSS仅使用统一的推送日和推送时间，如果要设置自定义RSS的推送时间，则可以将其title和url写到一个Recipe里面，再上传即可开始设置。


## 如何自定义封面？
KindleEar内置7个封面，默认随机选取，也可以配置为按周内日选取。你可以上传自己喜欢的封面来替换这些内置封面，入口在“高级设置”的“上传封面图像”菜单。
如果要单独给某个Recipe设置封面，则需要在其Recipe源代码中添加一个 cover_url 属性，可以为本地文件（如果是相对目录，则相对于KindleEar应用目录）或网络图像，比如：
```
cover_url = '/temp/mycover.jpg'
cover_url = 'application/images/mycover.jpg'
cover_url = 'https://www.google.com/mycover.jpg'
cover_url = False #no cover image
```
额外的，如果要自定义报头，则添加一个 masthead_url 属性，格式和 cover_url 一致。   


## 忘记密码了怎么办？
KindleEar不保存密码原文，无法取回密码。在登录时密码验证错误时会有一个“忘记密码？”链接，点击这个链接就可以使用创建账号时登记的email邮箱来重置密码。   


<a id="appspotmail"></a>
## 入站邮件功能怎么用？
如果您的应用是部署在Google cloud平台(GAE)，邮箱地址为：`xxx@appid.appspotmail.com` (xxx为任意合法字符串，appid为您的应用名)。     
如果使用Docker compose部署，邮箱地址为： `xxx@domain`，前提是需要开放25端口，并且在DNS服务器正确设置了MX记录。   

1. 要使用此功能，先要添加白名单，如果为 `*` 则允许所有邮件，否则格式为 `xx@xx.xx` 或 `@xx.xx`。  

2. 此邮箱将收到的邮件正文转换为邮件附件推送至你注册的Email邮箱。如果邮件中只有链接（多个链接则每行一个），则抓取链接的网页内容制作成电子书然后再推送。   

3. 如果在邮件主题最后添加了标识 !links，则不论邮件内容如何，KindleEar都只会提取邮件中的链接，然后抓取网页，制作成电子书发送至你的Kindle。这个功能最适合将网络连载网页直接发送至Kindle观看。   

4. 如果在邮件主题后添加了标识 !article，则忽略所有链接，直接将内容转换为电子书发送。   

5. 推送的电子书默认语言为自定义RSS的语言，如需要其他语种，可以在邮件主题后添加标识 !lang=en (将en替换为您需要的语种代码)。     

6. 默认推送至管理员注册的邮箱，如果要推送至其他用户的邮箱，则使用格式： `username__xxx@domain` 。（注意是双下划线）。   

7. 如果将电子书下载链接发送至 `book@domain` 则KindleEar直接下载对应的电子书并转发至注册的邮箱（注意后缀名有限制，不能发送可能有安全隐患的文件后缀比如exe等，zip文件能发送，但是zip文件内不能包含可能有安全隐患的文件）。    
GAE可邮件发送的后缀名列表参见：[Mail Python API Overview](https://cloud.google.com/appengine/docs/python/mail/#Python_Sending_mail_with_attachments)
（book/file/download邮件地址保留为下载电子书使用）。   

8. Amazon不再支持推送mobi文件，如果你有mobi文件('.mobi', '.prc', '.azw', '.azw3', '.pobi') 需要推送给Kindle，可以以附件形式发送邮件至 `convert@domain`，KindleEar将其转换为epub然后再推送给Amazon。   
注：mobi文件不能有DRM加密，否则转换失败。   

9. 发送至 `trigger@domain`，则触发一次手动投递。邮件标题为空或为all则完全等同于网页上的“现在投递”按钮。如果需要推送特定书籍，则在标题上写书籍名字，多个书籍名字使用逗号分隔。   

10. 发送至 `debug@domain` 的邮件则直接抓取邮件中的链接并直接发送HTML文件至管理员邮箱而不是Kindle邮箱。   


## 有的网站需要登录才能阅读文章的问题如何解决？
有些网站需要先注册账户然后登录后才能阅读和下载文章，对于此类网站，则可以在Recipe源代码中添加一个属性：
```
needs_subscription = True
```
然后订阅后即可以在对应Recipe的弹出菜单中选择“网站登录信息”，可以输入登录账号和密码。  
1. 需要执行javascript或要输入验证码的网站无法支持。  
2. 对于一些足够特殊和复杂的网站，可能你需要在书籍子类中重写 get_browser() 函数。   
3. 你输入的密码将加密保存，密钥为每个账号都不一样的8位随机字符串，有一定的安全性，而且我尽量照顾你的密码安全，你可以随时删除保存的密码信息，书籍退订后也马上删除密码，但因为密钥也保存在GAE上，所以不能保证很高的安全性，请自己明白并愿意承担其中的风险。   


## 订阅Recipe时“订阅”和“订阅（单独推送）”选项有什么区别？
“订阅”是合并推送，将所有按这个选项订阅的Recipe和自定义RSS都合并为一个文件推送，“订阅（单独推送）”是将这个Recipe单独创建一个文件推送，更适合一些生成文件比较大或有特殊推送时间的Recipe。   



## 推送的书籍太大导致推送失败？
每个邮件发送服务商对单个邮件的大小都是有限制的，比如GAE限制31.5MB，mailjet现在15MB等，如果附件超过限额，则会导致推送失败。   
1. 将"配置"页面的"设备类型"设置为Kindle，则所有图像文件都会缩小为 525x640 以下。   
2. 部分订阅源可以使用 "订阅（单独推送）"选项，可以将一个大的文件分割为几个小文件进行推送。  
3. 新建其他账号，不同的账号推送不同的订阅源，也可以减小单个推送文件的大小。   
4. "最旧文章"值设置小一些，避免包含多余的文章。   



## 书籍翻译功能在哪里，如何使用？
KindleEar移植了calibre的"Ebook Translator"插件，在抓取外语新闻时可以一并翻译，方便学习外语同时也可以有更广的新闻信息来源。    
数据翻译器默认禁用，需要逐个Recipe打开，每个Recipe可以有不同的设置。    
在订阅Recipe后，点击右边的弹出按钮，选择"书籍翻译器"按钮即可进入设置。   
* 译文位置: 左右对照翻译只适合于平板或电脑，并且有时候会导致排版错乱，电纸书一般选择上下对照翻译即可。  
* 原文/译文样式: 可以输入任意标准的CSS文本样式，比如：`color:#123456;font-style:italic`。   



## 如何使用书签小应用(Bookmarklet)，都有什么功能？
在"我的订阅"页面下方会显示几个书签小应用的链接，也称为Bookmarklet，提供一些便捷的功能。   
如果要使用，按住链接然后拖动至浏览器的书签栏即可。   
Bookmarklet是每个用户不同的，你当前看到的链接仅应用于你当前登录用户。  

* **发送到Kindle**:
1. 在电脑上浏览其他网站时，如果碰到一些文章比较长，希望在Kindle上阅读，可以直接点击此Bookmarklet，则KindleEar会抓取当前网页制作成电子书发送到您注册的Kindle邮箱。    
2. 有些网页的文章结构比较复杂，因 [正文提取算法](https://pypi.org/project/readability-lxml) 不够聪明，可能在Kindle上排版不好或丢失很多内容，为此，可以先选择希望推送的文章内容（可以包含图像文件），然后再点击此Bookmarklet。（真正的人工智能～）       
3. 如果是 gitbooks.io 的书籍，则KindleEar会抓取整本书的内容制作成电子书进行推送。    

* **在KindleEar订阅**:
用于便捷订阅RSS链接，在电脑上打开对应的RSS链接后，点击此Bookmarklet，则将当前URL和title填充到KindleEar的"自定义RSS"里面的文本框，仅此而已，少两次拷贝粘贴的动作，懒人专用。   

* **选择内容发送到Kindle**:
GAE平台专用，因为只有GAE平台直接有收邮件功能。   
使用方法是先选择网页部分内容，然后点击此Bookmarklet，则会打开一个小的gmail发送邮件窗口，自动将选择的文章内容填充到邮件的正文区域，然后发送给 xxx@appid.appspotmail.com 就可以推送到Kindle。    



## "我的订阅"的Recipe右上角的Emb等角标都是什么含义？
* Emb: Content embedded, 全文RSS，文章全文信息已经包含在xml文件里面。   
* Upl: Uploaded recipe, 用户自己上传的Recipe，如果没有这个角标就是内置的Recipe。   
* Sep: Separated, 此Recipe会推送为一个单独的文件。   
* Log: Login required， 此Recipe源网站需要订阅并登录才能抓取其内容，如果碰到此角标则需要配置登录信息，否则会抓取失败。  


## 我一次性导入了太多的自定义RSS怎么批量删除？   
* 可以在 "标题" 里面写 '#removeall#'，然后点击 "添加" 即可全部删除自定义RSS。   


## 如何将新的recipe文件保存到内置recipe库？
KindleEar提供了一个通过网页上传recipe文件的功能，在calibre的recipe有 [更新](https://github.com/kovidgoyal/calibre) 后，你可以仅仅上传您感兴趣的recipe而不需要重新部署KindleEar。   
但是如果你希望将recipe文件合并入内置库。    
1. 如果你还没有创建KindleEar本地运行环境，先运行 `pip install -r requirements.txt` 来保证脚本的正常运行。   
2. 将recipe文件拷贝到application/recipes目录，不需要删除 builtin_recipes.zip/builtin_recipes.xml， 除非你希望制作一个全新的只包含你选择的recipe的内置库。     
3. 执行tools/archive_builtin_recipes.py。    
4. 删除recipe文件。    
**注：** 可以直接使用calibre的 builtin_recipes.zip/builtin_recipes.xml。   



## 我还有更多问题，到哪里去问？
如果你碰到更多问题，可以到 [https://github.com/cdhigh/KindleEar/issues](https://github.com/cdhigh/KindleEar/issues) 去提交一个issue，然后等待答复，不过在提交问题之前，还是建议先搜索一下别人先前提交的issues，说不定已经有人重复提过了相关问题呢？   
如果没有别人提过类似问题，你在提交新问题的时候，建议附上 [GAE后台](https://console.cloud.google.com/appengine) 或你部署的平台的的Logs信息，以便定位问题，也可以得到更快的答复。   

