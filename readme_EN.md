# Brief Introduction
KindleEar is a web application to aggregate RSS for generating periodical mobi/epub file with images and send it to your kindle or your email automatically.

## The features included:
* Support calibre-like recipe file to aggress unlimited RSS or webpage.
* Support custom RSS, only title/url are needed, don't need to program.
* With account management, support several kindles.
* Generate periodical mobi/epub file with images.
* Deliver news feeds to your kindle dialy automatically.
* Built-in shared library, can share links with others and subscribe links from others.
* Website support multi-languages.
* Powerful and convenient mail-transfering service.
* Integration with Evernote/Pocket/Instapaper.

# Deployment
1. [Create a Google account](https://accounts.google.com/SignUp) and [Turn on Access for less secure apps](https://www.google.com/settings/security/lesssecureapps).  

2. [Create an application](https://console.developers.google.com/project).  

3. Install [Python 2.7.x](https://www.python.org/downloads/).  

4. Install [GAE SDK](https://cloud.google.com/appengine/downloads).  

5. [Download KindleEar](https://github.com/cdhigh/KindleEar/archive/master.zip) and uncompress it into a directory for example: *c:\kindleear*.  

6. Modify some variable in app.yaml/module-worker.yaml/config.py.  

  File              | To be changed | Description             |  
-------------------|-------------|-----------------------|  
app.yaml           | application | Your Application Id    |  
module-worker.yaml | application | Your Application Id    |  
config.py          | SRC_EMAIL   | Your Gmail Address          |  
config.py          | DOMAIN      | appid@appspot.com        |  
config.py          | TIMEZONE    | Your timezone         |

> the lines application and version in yaml have to be commented if you will deploy it by using gcloud.

7. Choose 7.1 or 7.2 to deploy it.  

7.1 using appcfg.py  
	* `c:\python27\python.exe appcfg.py update KindleEarFolder\app.yaml KindleEarFolder\module-worker.yaml`  
	* `c:\python27\python.exe appcfg.py update KindleEarFolder`  
  
7.2 using gcloud  
    * Delete the first two lines of app.yaml and module-worker.yaml [application and version]  
    * `gcloud auth login`  
    * `gcloud config set project YourApplicationId`  
    * `gcloud app deploy --version=1 KindleEarFolder\app.yaml KindleEarFolder\module-worker.yaml`    
    * `gcloud app deploy --version=1 KindleEarFolder`  
    * [If needed] `gcloud datastore indexes create KindleEarFolder\index.yaml`  

8. After finished, you can open the website *'http://appid.appspot.com'* (appid is the name of your application),  
For example the author's site: <http://kindleear.appspot.com>  
**The initial username is 'admin', password is 'admin', please change the password immediately after first login.**  

9. More details could be found in [FAQ](http://htmlpreview.github.io/?https://github.com/cdhigh/KindleEar/blob/master/static/faq_en.html).

# Deployment simplified
If you don't want to intall GAE SDK and python, you have another choice.  

1. [Download KindleEar](https://github.com/cdhigh/KindleEar/archive/master.zip) and uncompress it (Change the name of folder to 'KindleEar').  
2. [Download KindleEar-Uploader](https://drive.google.com/folderview?id=0ByRickMo9V_XNlJITzhYM3JOYW8&usp=sharing) and unzip it.  
3. Put KindleEar folder into Uploader directory, double-click uploader.bat to start process of deployment.  

# License
   KindleEar is Licensed under the [AGPLv3](http://www.gnu.org/licenses/agpl-3.0.html) license.

# Contributors
* @rexdf <https://github.com/rexdf> 
* @insert0003 <https://github.com/insert0003> 
* @zhu327 <https://github.com/zhu327> 
* @lord63 <https://github.com/lord63> 
* @th0mass <https://github.com/th0mass> 
* @seff <https://github.com/seff> 
* @miaowm5 <https://github.com/miaowm5> 
* @bookfere <https://github.com/bookfere> 
