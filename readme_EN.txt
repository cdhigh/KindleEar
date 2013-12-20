1. KindleEar is a web application to aggregate rss for generating periodical mobi file with images 
   and send it to your kindle automatically.
   The features:
   1.Support calibre-like recipe file to aggress RSS.
   2.Support custom rss, input title and url to deliver, dont need to program.
   3.With account management, support several kindles in a application.
   4.Generate periodical mobi file with images.
   5.Deliver news feeds to your kindle automatically.
   6.website support multi-languages.

2. Deployment step by step
   1.Register a GAE account and create a application : https://appengine.google.com/
   2.Download GAE SDK and install: https://developers.google.com/appengine/downloads
   3.Install Python 2.7.x
   4.Download all files of this application and uncompress it into a directory for example: c:\kindleear.
   5.Modify the first line of app.yaml, change kindleear to name of application that you create in step 1.
   6.Modify variable SrcEmail and TIMEZONE of config.py
      SRC_EMAIL : your gmail address that used to register a GAE account in step 1.
      TIMEZONE : your timezone
   7.Execute command in directory GAE SDK(default is C:\Program Files\Google\google_appengine)
      'c:\python27\python.exe appcfg.py update c:\kindleear' (c:\kindleear is directory that you put files in step 4)
      input email address and password and wait it finish.
      after finished, you can open the website 'appid.appspot.com' (appid is name of your application)
      for example site of author: kindleear.appspot.com
      the initial username is 'admin', password is 'admin', please change it immediately after login.
   8.more details can be found in faq.
   9.If you don't want to intall GAE SDK and python, you have another choice, download 'uploader' from:
     https://drive.google.com/folderview?id=0ByRickMo9V_XNlJITzhYM3JOYW8&usp=sharing
     put kindleear folder into uploader directory, then double-click uploader.bat.
  
3. License
   KindleEar is Licensed under the GPL license: http://www.gnu.org/licenses/gpl.html