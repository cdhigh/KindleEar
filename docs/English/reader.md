---
sort: 4
---

# Online Reading

## Overview

KindleEar supports email delivery and online reading. Built-in an online reader specially optimized for e-ink screens.    
The advantage of email delivery is the ability to read offline. After downloading to an e-book device, you can carry it with you and read it anytime.    
The advantage of online reading is that it does not occupy space on the e-book device and does not require manual deletion of e-books, moreover, it can support more e-book devices.    

## Activate and Configure

1. Set the `EBOOK_SAVE_DIR` to a directory with write permissions. This can be modified in `config.py` or passed through an environment variable.

2. Online reading is supported only on Docker/VPS platforms. If you are using the pre-built Docker image from the author, online reading is enabled by default. (GAE platform cannot support online reading due to lack of writable disk permissions.)

3. It is recommended to set an appropriate "Web shelf" time on the "Settings" page. KindleEar will automatically clean up e-books that exceed this time, making it worry-free and effortless.    

4. The online reading page is optimized for e-ink screens, using pagination instead of scrolling. The page is divided into 5 clickable areas:
   * The top-left corner defaults to activating the dictionary lookup mode, which can be adjusted to 'Open Previous Article' through the options menu.    
   * Top right corner: Next article
   * Middle top area: Open menu
   * Middle left side: Previous page
   * Remaining page area: Next page, convenient for switching to the next page regardless of holding the book with the left or right hand
   * Clicking the next page area on the last page of the current article automatically opens the next article
   * Clicking the previous page area on the first page of an article automatically opens the previous article  

5. Keyboard Shortcuts
   * Spacebar, right arrow key, PageDown - Next article
   * Left arrow key - Previous article
   * Up arrow key - Previous book
   * Down arrow key - Next book

6. The Kindle browser does not support cookie persistence, requiring account and password to be entered each time it's opened. To avoid this inconvenience, you can add account and password query strings to bookmarks:     
`https://youdomain/reader?username=YourName&password=YourPassword`     

7. If you need some subscriptions to be pushed and others only for online reading, you can create two accounts, one for pushing and one for online reading.


## Dictionary

Due to the limitations of the Kindle browser, only limited click-to-translate functionality is supported.     
Highlighting for translation and phrase translation is not supported. If you need extensive dictionary usage, it's recommended to push to Kindle for reading.     
The principle of the dictionary function is to automatically extract the word closest to the clicked area. Words need to be surrounded by spaces, so translation of Chinese, Japanese, and Korean (CJK) is not supported as source languages (though they can be target languages).     

The extracted word is sent to your deployed KindleEar site for translation, and the response is displayed.   

### Installing Dictionaries
1. KindleEar supports online dictionaries such as [dict.org](https://dict.org/), [dict.cc](https://www.dict.cc/), [dict.cn](http://dict.cn/), [Merriam-Webster](https://www.merriam-webster.com/), [Oxford](https://www.oxfordlearnersdictionaries.com/). These dictionaries require no installation and are ready to use out of the box.    

2. KindleEar also supports offline dictionaries in the stardict format. After downloading the corresponding dictionary, unzip it into the `data/dict` directory. You can organize different dictionaries into subdirectories. Then, restart the KindleEar service to refresh the dictionary list.    

3. The first time you look up a word in the offline dictionary, it may be slow because it needs to create an index file (suffix: trie), After that, it will be much faster. 
If you are using a large dictionary (for example, above several hundred megabytes), the indexing process will consume a significant amount of memory. If the server has limited memory, the indexing might fail. You can first use the dictionary on your local machine to look up a word and generate the "trie" file, then copy it to the corresponding directory on the server.    

4. By default, American English morphology queries are supported (tense, voice, plural etc.).    
If you need to support morphology rules for other languages, please download the corresponding Hunspell format files (.dic/.aff), and then copy them to `data/dict/morphology` (create it if not exists). Be careful not to store them in a subdirectory.    
KindleEar will automatically use the morphology rules that match the book's language.   
As for where to download Hunspell/MySpell morphology files, you can search on websites such as GitHub or SourceForge.    
[LibreOffice](https://github.com/LibreOffice/dictionaries)    
[Firefox](https://addons.mozilla.org/en-US/firefox/language-tools/)    
[sztaki](http://hlt.sztaki.hu/resources/hunspell/)     
[wooorm](https://github.com/wooorm/dictionaries)    


### Using Dictionaries
1. To use the dictionary function, first configure the translation engine and languages in "Advanced"/"Dictionary" options page.   

2. When encountering an unfamiliar word while reading.  
2.1. If the top-left corner dictionary mode is activated (by default), clicking on the top-left corner of the page will enter the dictionary lookup mode.     
2.2. Open the menu and click on the 'Dictionary' icon.     
After entering the dictionary lookup mode, a dictionary indicator will appear in the top-left corner of the page. Click on the word you want to look up, and the lookup mode will automatically exit after the lookup.   

3. Click anywhere inside the pop-up dictionary box to close it.   
