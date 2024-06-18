---
sort: 6
---
# FAQ


## What is full-text RSS?
Full-text RSS is the term I use for this type of RSS, and I don't know what the correct name is. In Calibre, it's called Embedded Content. This type of RSS already provides the full content of the article in its XML file. You only need to make one connection to get the full content of many articles, instead of having to connect to the network for each article like with regular RSS, saving a lot of time and other resource consumption.
How to confirm whether the RSS you want to subscribe to is full-text RSS? It's simple. Use a browser to open the corresponding link of the RSS and see if all the article content is already there. If it is, then it's full-text RSS. If only article summaries are provided, then it's not.



## Can full-text RSS be treated as summary RSS, and vice versa?
Of course, full-text RSS can be treated as summary RSS, which ignores the article content provided in the RSS link and directly fetches it from the original link, but it takes a little longer, resulting in a decrease in the number of supported RSS feeds. If it's summary RSS, it cannot be treated as full-text RSS, otherwise it will result in incomplete article content.



## How to customize the delivery time for a Recipe?
In addition to setting a unified delivery day and time on the settings page, each Recipe can customize its own unique delivery day and time. Once set, the unified time setting will be ignored for this Recipe. The method is to click on the circular button next to a Recipe in the "Subscribed" section of "My Feeds," then use the "Customize delivery time" button that pops up to set it. You can set it to push only on certain days or multiple times a day.
However, custom push time is only applicable to built-in and uploaded Recipes. Custom RSS feeds use only the unified time set. If you want to set the push time for a custom RSS feed, you can write its title and URL into a Recipe, and then upload it to start setting.



## How to customize the cover?
KindleEar has 7 built-in covers, which are randomly selected by default or can be configured to be selected by day of the week. You can upload your own favorite covers to replace these built-in covers. The entry is in the "Cover Image" under "Advanced" section.  
If you want to set a cover for a specific Recipe, you need to add a cover_url attribute in its Recipe source code. It can be a local file (if it's a relative directory, it's relative to the KindleEar application directory) or a web image, for example:
```
cover_url = '/temp/mycover.jpg'
cover_url = 'application/images/mycover.jpg'
cover_url = 'https://www.google.com/mycover.jpg'
cover_url = False #no cover image
```
Additionally, if you want to customize the masthead, add a masthead_url attribute, which has the same format as cover_url.   



## What if I forget my password?
KindleEar does not store passwords in plain text and cannot retrieve them. If login fails due to password verification, a "Forgot Password?" link is provided. Click on this link to reset your password using the email address registered when creating your account.



<a id="appspotmail"></a>
## How to Use the Inbound Mail Function?    
If your application is deployed on the Google Cloud Platform (GAE), the email address is: `xxx@appid.appspotmail.com` (where xxx is any valid string, and appid is your application name).  
If deployed using Docker Compose, the email address is: `xxx@domain`, remember to open port 25 and set MX records correctly in the DNS server.    

1. To use this function, you need to add whitelist first. If set to `*`, it allows all emails. Otherwise, the format should be `xx@xx.xx` or `@xx.xx`.    

2. This email will convert the received email body into e-book and push them to your registered email. If the email only contains links (one link per line), it will fetch the web content of the links and create an e-book before pushing.    

3. If email subject contains the identifier `!links`, regardless of the email content, KindleEar will only extract the links from the email, then fetch the webpages and send them as e-books to your Kindle. This feature is best suited for sending serialized web content directly to Kindle for viewing.   

4. If the identifier `!article` is present in the subject, all links will be ignored, and the content will be directly converted into an e-book for delivery.      

5. The default language of the e-book is same as of the custom RSS. If you need another language, you can add the identifier `!lang=en` (replace `en` with the language code you need) after the email subject.   

6. By default, the e-book is pushed to the administrator's registered email. If you want to push it to another user's email, use the format: `username__xxx@domain`. (Note the double underscore)   

7. If you send the e-book download link to `book@domain`, KindleEar will directly download the corresponding e-book and forward it to the registered email. (Note: there are restrictions on file extensions; you cannot send file extensions that may have security risks, such as exe, zip files are allowed, but zip files cannot contain files with potential security risks.)    
The suffix list that GAE can send emails to see: [Mail Python API Overview](https://cloud.google.com/appengine/docs/python/mail/#Python_Sending_mail_with_attachments) (book/file/download email addresses are reserved for downloading e-books).        

8. Amazon no longer supports pushing mobi format. If you have mobi files ('.mobi', '.prc', '.azw', '.azw3', '.pobi') that need to be sent to your Kindle, you can send them as an attachment via email to `convert@domain`. KindleEar will convert them to epub and then send them to Amazon.   
Note: Mobi files must not have DRM encryption; otherwise, the conversion will fail.   

9. Sending to `trigger@domain` triggers a manual delivery. If the email subject is empty or 'all', it is equivalent to the "Deliver Now" button on the website. If specific books need to be pushed, write their names in the subject, separated by commas.    

10. Emails sent to `debug@domain` will directly fetch the links from the email and send HTML files directly to the administrator's email instead of the Kindle mailbox.    



## What if some websites require login to read articles?
Some websites require registering an account and logging in to read and download articles. For such websites, you can add an attribute in the Recipe source code:
```
needs_subscription = True
```
Then, after subscribing, you can select "Website Login Information" from the corresponding Recipe's popup menu to enter your login account and password.
1. Websites that require executing JavaScript or entering a captcha are not supported.
2. For some sufficiently special and complex websites, you may need to override the get_browser() function in the book subclass.
3. The password you enter is encrypted and saved, with a unique 8-character random string key for each account, which has a certain level of security. I try my best to take care of your password security. You can delete the saved password information at any time, and the password is also deleted immediately after unsubscribing from the book. However, because the key is also saved in database, the security cannot be guaranteed to be very high. Please understand and be willing to bear the risks involved.



## What's the difference between "Subscribe" and "Subscribe (Deliver Separately)"?
"Subscribe" is for combined delivery, which combines all Recipes and custom RSS feeds subscribed to with this option into one file for delivery. "Subscribe (Deliver Separately)" creates a separate file for this Recipe for delivery, which is more suitable for Recipes that generate large file or have special delivery times.



## The book failed to be pushed due to it is too large?
Each send mail service provider has limitations on the size of individual emails. For example, GAE restricts it to 31.5MB, while Mailjet currently allows 15MB only. If the attachment exceeds this limit, it will result in a failed push.  
1. Set the "Device Type" to "Kindle", all image files will be resized to below 525x640 pixels.  
2. Subscribe some recipes by using the "Subscribe (Deliver Separately)" button to split a large file into several smaller ones.   
3. Create additional accounts, and push different recipes with different accounts to reduce the size of individual files.   
4. Set the "Oldest article" option smaller to avoid including unnecessary articles.    



## Where is the book translation function and how do I use it?
KindleEar has ported the "Ebook Translator" plugin from calibre, which can translate foreign language news while fetching, making it convenient to learn foreign languages and also have a wider range of news sources.  
The feature translation is disabled by default and needs to be enabled for each Recipe individually, with each Recipe having different settings.   
After subscribing to a recipe, click the floating button on the right and select the "Translator" button to enter settings page.   
* Translation position: Left-right two-columns layouts are only suitable for tablets or computers, and sometimes may cause layout issues. E-readers generally choose top-bottom layouts.   
* Original/Translated text style: You can input any standard CSS text style, such as: `color:#123456;font-style:italic`.   



## How to Use Bookmarklet?
At the bottom of the "Feeds" page, you'll find several bookmarklet links, which offer some convenient functions.   
To use them, simply drag and drop the links to your browser's bookmark bar.  
Each user of KindleEar has their own unique Bookmarklet links, and the ones you see currently apply only to your logged-in account.   

* **Send to Kindle**:
1. While browsing other websites on your computer, if you prefer to read some articles on your Kindle, simply click this Bookmarklet. KindleEar will then grab the current webpage and create an eBook to send to your Kindle email.   
2. Some web pages may have complex article structures, and due to a limit of [readability algorithm](https://pypi.org/project/readability-lxml), the formatting on Kindle might not be optimal or some content might be lost. In such cases, you can first select the desired article content (which may include image files) and then click this Bookmarklet.    
3. For books on gitbooks.io, KindleEar will grab the entire book's content and send it as an eBook.  

* **Subscribe with KindleEar**:
This function is for conveniently subscribing to RSS links. When you open the corresponding RSS link on your computer and click this Bookmarklet, the current URL and title will be filled into the text field under "Custom RSS" in KindleEar. It saves you a couple of copy-paste actions - perfect for lazy people.    

* **Kindleify Selection**:
Exclusive to the GAE platform, as only the GAE platform has inbound email feature.     
You should select some webpage's contents, then click this Bookmarklet. It will open a small Gmail window for sending an email, automatically filling the selected article content into the body of the email. Then, just send it to xxx@appid.appspotmail.com for pushing it to Kindle.   



## What do the sup text of the Recipe mean?
* Emb: Content embedded, indicates that the full article content is embedded within the XML file for full-text RSS.   
* Upl: Uploaded recipe, denotes a recipe uploaded by the user. If this icon is absent, it signifies a built-in recipe.   
* Sep: Separated, indicates that this recipe will be pushed as a separate file.   
* Log: Login required, indicates that the source website of this recipe requires subscription and login to fetch its content. If this icon appears, login information needs to be configured, otherwise the fetch will fail.   



## How do I bulk delete too many accidentally imported custom RSS feeds?   
* You can write '#removeall#' in the "Title" field, then click "Add" to delete all custom RSS feeds at once.   



## How to save new recipe files to the builtin recipe library?
KindleEar provides a feature to upload recipe files via the web page.   
After Calibre [updated](https://github.com/kovidgoyal/calibre) the recipes, you can simply upload the recipe files you are interested in without the need to redeploy KindleEar.   
However, if you wish to merge recipe files into the built-in library:   
1. If you haven't already created a local running environment for KindleEar, first run pip install -r requirements.txt to ensure the scripts run correctly.   
2. Copy the recipe files to the application/recipes directory. There is no need to delete builtin_recipes.zip/builtin_recipes.xml unless you want to create a brand new built-in library containing only the recipes you have selected.       
3. Run tools/archive_builtin_recipes.py.      
4. Delete the recipe files.    
**Note:** You can directly use calibre's `builtin_recipes.zip` and `builtin_recipes.xml`.   



## I have more questions, where can I ask?
If you have more questions, you can submit an issue at [https://github.com/cdhigh/KindleEar/issues](https://github.com/cdhigh/KindleEar/issues) and wait for a reply. Before submitting a question, it's recommended to search for previously submitted issues first. Maybe someone has already submitted a similar issue? If no one has submitted a similar issue, when you submit a new one, it's recommended to attach the Logs information of [GAE backend](https://console.cloud.google.com/appengine) or the platform you deployed to for problem location, which can also get you a faster reply.
