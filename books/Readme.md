# Book目录说明

1. 概述
    此应用根目录下的books目录存放自定义RSS设置，每个文件为一本"书"，对应推送到kindle的一本书。
    应用启动后会自动读取此目录下的所有py文件，动态导入，并显示在网页“我的订阅”下，可以选择是否推送。
    books目录下的文件除了`__init__.py`和`base_book.py`，其他的文件都可以随意删除，如果你不需要的话。
    在books目录下删除的“书籍”会在一天内从数据库中清除。

2. py文件格式

	* py文件建议为UTF-8格式，特别是里面有中文的话。

      所以每个py文件的头一行建议为：

      `# -*- coding:utf-8 -*-`
      或者：
      ```
      #!/usr/bin/env python3
      # -*- coding:utf-8 -*-
      ```
	* 每个py文件都要实现一个函数getBook()，返回书籍实际定义的"类"对象：
      ```
	    def getBook():
        	return Qiushibaike
  	  ```
	* 每本书为一个类(类名最好不要和文件名完全一样)，必须实现的接口只有一个：
    `Items(self)`
    它是一个生成器或者返回一个迭代器。
    每次返回一个命名元组，可能为 ItemHtmlTuple 或 ItemImageTuple

	* 上面已经说完了书籍定义的一切，所以如果你精通python，就可以自己写自己的书籍类了。

	* 不过如果你偷懒，也可以继承base模块中定义的两个书籍模板之一来定制自己的书籍类。
    下一节介绍如何定制。

3. 书籍类定制方法
   写过或看过calibre的recipe的基本上就直接会了。
   因为calibre的recipe模块依赖挺多的，我时间不够，偷懒了，就不移植了，直接根据
   recipe的外形写了一个处理模块。
   * 根据RSS类型，从base模块中导入不同的书籍基类
     `from base_book import BaseFeedBook
     from base_url_book import BaseUrlBook
     from base_webpage_book import BaseWebpageBook
     from base_comic_book import BaseComicBook`
   * 如果你感兴趣的网站不提供RSS订阅，则可以继承BaseWebpageBook直接连接网页提取信息。
   * 子类能定制的参数都在BaseFeedBook类的定义中，注释很详细。
   * 处理HTML的BeautifulSoup为4.x版本。
   * `cartoonmadbase.py`提供了抓取漫画图片的例子。
