# Announcement
Starting from 2024-01-06, the author has begun the migration of KindleEar to Python 3. The final completion time of the migration cannot be assessed temporarily. Before the announcement is complete, the code in this repository cannot be deployed. If you need to deploy, please download the [v1.26.9 code archive](https://github.com/cdhigh/KindleEar/releases/tag/1.26.9).


# Brief Introduction
KindleEar is a web application to aggregate RSS for generating periodical mobi/epub file with images and send it to your kindle or your email automatically.

## The features included:
* Support calibre-like recipe file to aggress unlimited RSS or webpage.
* Support custom RSS, only title/url are needed, don't need to program.
* With account management, support several kindles.
* Generate periodical mobi/epub file with images.
* Deliver news feeds to your kindle daily automatically.
* Built-in shared library, can share links with others and subscribe links from others.
* Website support multi-languages.
* Powerful and convenient mail-transfering service.
* Integration with Evernote/Pocket/Instapaper.

# Deployment
1. [Create a Google account](https://accounts.google.com/SignUp) and [Turn on Access for less secure apps](https://www.google.com/settings/security/lesssecureapps).  

2. [Create an application](https://console.developers.google.com/project).  

3. Install [Python 2.7.x](https://www.python.org/downloads/).  

4. Install [GAE SDK](https://storage.cloud.google.com/cloud-sdk-release).  note: choose some version before 273.0.  
   [google-cloud-sdk-273.0.0-windows-x86_64-bundled-python.zip](https://storage.googleapis.com/cloud-sdk-release/google-cloud-sdk-273.0.0-windows-x86_64-bundled-python.zip)
    [google-cloud-sdk-273.0.0-darwin-x86.tar.gz](https://storage.googleapis.com/cloud-sdk-release/google-cloud-sdk-273.0.0-darwin-x86.tar.gz)
    [google-cloud-sdk-273.0.0-darwin-x86_64.tar.gz](https://storage.googleapis.com/cloud-sdk-release/google-cloud-sdk-273.0.0-darwin-x86_64.tar.gz)
    [google-cloud-sdk-273.0.0-linux-x86.tar.gz](https://storage.googleapis.com/cloud-sdk-release/google-cloud-sdk-273.0.0-linux-x86.tar.gz)
    [google-cloud-sdk-273.0.0-linux-x86_64.tar.gz](https://storage.googleapis.com/cloud-sdk-release/google-cloud-sdk-273.0.0-linux-x86_64.tar.gz)
    [google-cloud-sdk-273.0.0-windows-x86-bundled-python.zip](https://storage.googleapis.com/cloud-sdk-release/google-cloud-sdk-273.0.0-windows-x86-bundled-python.zip)
    [google-cloud-sdk-273.0.0-windows-x86.zip](https://storage.googleapis.com/cloud-sdk-release/google-cloud-sdk-273.0.0-windows-x86.zip)
    [google-cloud-sdk-273.0.0-windows-x86_64.zip](https://storage.googleapis.com/cloud-sdk-release/google-cloud-sdk-273.0.0-windows-x86_64.zip)

5. [Download KindleEar](https://github.com/cdhigh/KindleEar/archive/master.zip) and uncompress it into a directory for example: *c:\kindleear*.  

6. Modify some variable in app.yaml/module-worker.yaml/config.py.  

  File              | To be changed | Description             |  
-------------------|-------------|-----------------------|  
app.yaml           | application | Your Application Id    |  
module-worker.yaml | application | Your Application Id    |  
config.py          | SRC_EMAIL   | Your Gmail Address          |  
config.py          | DOMAIN      | appid@appspot.com        |  
config.py          | TIMEZONE    | Your timezone         |

> the lines 'application' and 'version' in yaml have to be commented if you will deploy it by using gcloud.

7. Deployment
    * Delete the first two lines of app.yaml and module-worker.yaml [application and version]  
    * `gcloud auth login`  
    * `gcloud config set project YourApplicationId`  
    * `gcloud app deploy --version=1 KindleEarFolder\app.yaml KindleEarFolder\module-worker.yaml`    
    * `gcloud app deploy --version=1 KindleEarFolder`  
    * [If some error after deployment.] 
      `gcloud datastore indexes create index.yaml`
      `gcloud app deploy --version=1 app.yaml queue.yaml`
      `gcloud app deploy --version=1 app.yaml cron.yaml`
      `gcloud app deploy --version=1 app.yaml dispatch.yaml`  

8. After finished, you can open the website *'http://appid.appspot.com'* (appid is the name of your application),  
For example the author's site: <http://kindleear.appspot.com>  
**The initial username is 'admin', password is 'admin', please change the password immediately after first login.**  

9. More details could be found in [FAQ](http://htmlpreview.github.io/?https://github.com/cdhigh/KindleEar/blob/master/static/faq_en.html).

# Deployment simplified
If you don't want to intall GAE SDK and python, you have another choice.  
Reference code repository <https://github.com/bookfere/KindleEar-Uploader> and tutorial <https://bookfere.com/post/19.html#ke_2_1> (in Chinese, but you can translate it by Google).  
This method can be deployed directly in the console window of the GAE background.  

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
