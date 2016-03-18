#Changelog for KindleEar

##1.22.3
  1. bugfix: ilegal tag name (unicode name) in xml cause failure in parsing a xml file.

##1.22.2
  1. Mail-transfer module suppoorts '!links' and '!article' that indicate crawl links in mail or send text only.
  2. kindle_email field suppoorts multiple email address separated with comma or semicolon.

##1.22.1
  1. Replace some modules with lastest version.

##1.22
  1. Rewrite manager of "Feed" via AJAX technology, provide better user experience.

##1.21.1
  1. Add a feature to save an article to Instapaper.

##1.21
  1. Add a feature to save an article to Pocket.

##1.20.28
  1. update book "xueqiu".

##1.20.27
  1. An single email of appspotmail supports more links.

##1.20.26
  1. Improve performance of loading webpage via inline base64 image technology.

##1.20.25
  1. enhance decode process to avoid some garbled chars.

##1.20.24
  1. bugfix: Cover missing when pushing custom RSS only with option 'merge books' checked.

##1.20.23
  1. Get rid of options 'title dd/mm' and 'title mm/dd' in title's format for compatibility.

##1.20.22
  1. bugfix: unicode chars in URL crash the app when export it to OPML.
  2. bugfix: timeout during fetching Official Account of Wechat crash the app.
  
##1.20.21
  1. Add etag to http's header to reduce data traffic.

##1.20.20
  1. fix wrong decoding of some xml files.

##1.20.19
  1. fix problem of import failed of pycrypto.

##1.20.18
  1. Break through the anti-creeper of Official Account of Wechat [zhu327](https://github.com/zhu327/rss).
  2. Remove cover when fetching articles from links in email.
  
##1.20.17
  1. add a num of article to title of category.
  
##1.20.16
  1. A option added for choose title come from webpage or feed.
  
##1.20.15
  1. bugfix: weixinbase failed when decode some article.

##1.20.14
  1. bugfix: change address of rss of book 'dapenti.py'.

##1.20.13
  1. bugfix: a picture as an article (without html wraper) will crash KindleEar.
  
##1.20.12
  1. quote url when export subscriptions to opml.

##1.20.11
  1. "Import Feeds" supports nested outlines in OPML file.

##1.20.10
  1. bugfix: some complex articles cause failure of delivery. 
  
##1.20.9
  1. New feature: import list of custom rss from a opml file. 
  2. New feature added by seff: add a switch 'Separate' to books. book is pushed to kindle separately if it's checked.


##1.20.8
  1. a book <gongshi> added by mcfloundinho.
  
##1.20.7
  1. bugfix:trigger@appid.appspotmail.com trigger task deliver failed.
  
##1.20.6
  1. bugfix: refix a bug in process cookie of module urlopener.
  
##1.20.5
  1. Add book nfzm written by mcfloundinho.
  2. bugfix: fix a bug in process cookie of module urlopener.

##1.20.4
  1. Update Turkish translation.

##1.20.3
  1. fix book 'TEDxBohaiBay'.

##1.20.2
  1. Supports some webpage which images take a 'data-src' attribute to load asynchronous content.
  
##1.20.1
  1. Paste all covers into one when merge books into one. DEFAULT_COVER_BV=None (default value) to enable the feature.
  2. bugfix: send mail to evernote failed. (bug from version 1.13)
  
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
