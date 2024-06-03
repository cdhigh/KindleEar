---
sort: 4
---

# Online Reading

## Overview

KindleEar supports email delivery and online reading.    
The advantage of email delivery is the ability to read offline. After downloading to an e-book device, you can carry it with you and read it anytime.    
The advantage of online reading is that it does not occupy space on the e-book device and does not require manual deletion of e-books, moreover, it can support more e-book devices.    

## Activate and Configure

1. Set the `EBOOK_SAVE_DIR` to a directory with write permissions. This can be modified in `config.py` or passed through an environment variable.

2. Online reading is supported only on Docker/VPS platforms. If you are using the pre-built Docker image from the author, online reading is enabled by default. (GAE platform cannot support online reading due to lack of writable disk permissions.)

3. It is recommended to set an appropriate "Web shelf" time on the "Settings" page. KindleEar will automatically clean up e-books that exceed this time, making it worry-free and effortless.    

4. The online reading page is optimized for e-ink screens, using pagination instead of scrolling. The page is divided into 5 clickable areas:
   * Top left corner: Previous article
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

6. The Kindle browser does not support persistent cookies, so you need to enter your username and password each time you open it. To avoid this hassle, you can add your username and password in the query string of a bookmark, e.g., `https://yourdomain/reader?username=yourname&password=yourpassword`. Note that storing plain text passwords may be insecure, so consider this carefully.

7. If you need some subscriptions to be pushed and others only for online reading, you can create two accounts, one for pushing and one for online reading.

## Dictionary Function

Due to the limitations of the Kindle browser, only limited click-to-translate functionality is supported.     
Highlighting for translation and phrase translation is not supported. If you need extensive dictionary usage, it's recommended to push to Kindle for reading.     
The principle of the dictionary function is to automatically extract the word closest to the clicked area. Words need to be surrounded by spaces, so translation of Chinese, Japanese, and Korean (CJK) is not supported as source languages (though they can be target languages).     

The extracted word is sent to your deployed KindleEar site for translation, and the response is displayed.   

1. To use the dictionary function, first configure the translation engine and languages in "Advanced" | "Reader" options page.   

2. When encountering an unfamiliar word while reading, open the menu, select "Dictionary" to enter dictionary mode (no indication/tips is shown). Click the word to be queried, and dictionary mode will automatically exit after the query. To query again, click "Dictionary" in the menu again.    
