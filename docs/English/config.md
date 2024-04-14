---
sort: 2
---
# Configuration

<a id="baseconfig"></a>
## Base config
Regardless of the platform you deploy to, the first step is to correctly configure config.py.     
This section describes several simple configuration items, with more detailed descriptions of other configuration items in the subsequent sections.     

| Configuration Item | Meaning                                                |
| ------------------ | ------------------------------------------------------ |
| APP_ID             | Application identifier; for GAE platform, it's the app ID, while for other platforms, it's used to identify database and other resources |
| APP_DOMAIN         | Domain name of the deployed application                 |
| KE_TEMP_DIR        | Temporary directory for creating eBooks; if empty, temporary files are stored in memory |
| DOWNLOAD_THREAD_NUM| Number of threads for downloading web pages; the target platform needs to support multithreading, with a maximum value of 5 |
| ALLOW_SIGNUP       | Whether to allow user registration; "yes" - Users can register autonomously (with the option to restrict via invitation codes), "no" - means account creation is done by administrators |
| SECRET_KEY         | Encryption key for browser session, recommended to change, any string is acceptable |
| ADMIN_NAME         | Administrator's username                                |
| POCKET_CONSUMER_KEY| Used for Pocket's read-later service; you can use your own key or use this one directly |
| HIDE_MAIL_TO_LOCAL| Whether to allow saving generated emails locally for debugging or testing purposes |




## Database Selection
The database is used to store application configuration data and subscription data.      
Thanks to the SQL database ORM library [peewee](https://pypi.org/project/peewee/) and the NoSQL database ODM library [weedata](https://github.com/cdhigh/weedata) created by the author for KindleEar, KindleEar supports many types of databases, including: datastore, sqlite, mysql, postgresql, cockroachdb, mongodb, redis, pickle.       
It basically covers the mainstream databases on the market and is more suitable for cross-platform deployment. You can use whatever database the platform supports.        
If the target platform supports both SQL and NoSQL, it is advisable to use NoSQL. Its major advantage is that in case of future upgrades requiring modifications to the database structure, NoSQL will not affect the existing data, whereas SQL would delete the original data.      
The amount of data in this application is very small, to be precise, very, very small, usually just a few dozen lines of data. Choosing any database will not have any impact on resource consumption and performance. Even using a simple text file as a database may be faster than other formal databases.      




### datastore
Datastore is Google's NoSQL database, and we will be using the Datastore mode of Firebase. If you want to deploy to Google Cloud, basically, you can only choose Datastore because it has free quotas.       
To use Datastore, the parameter configuration is as follows:    
```python
DATABASE_URL = 'datastore'
```



### SQLite
SQLite is a single-file database. It is suitable for platforms with local file system read and write permissions, especially resource-constrained systems such as Raspberry Pi and various derivatives.   
The database file path support both absolute path and relative path, with the project directory as the base directory for relative path.   
To use SQLite, the parameter configuration is as follows:    
```python
#template:
DATABASE_URL = 'sqlite:////path/to/database.db'
#examples:
DATABASE_URL = 'sqlite:////C:/Users/name/kindleear/site.db'
DATABASE_URL = 'sqlite:////home/username/dbfilename.db'
DATABASE_URL = 'sqlite:///dbfilename.db'  #relative path
```



### MySQL/PostgreSQL/CockroachDB
These are typical enterprise-level SQL databases. It's like using a cannon to kill a mosquito, but if the platform supports it, there's no harm in using them directly.      
Parameter configuration is as follows:   
```python
#template:
DATABASE_URL = 'mysql://username:password@hostname:port/database_name'
DATABASE_URL = 'postgresql://username:password@hostname:port/database_name'

#examples:
DATABASE_URL = 'mysql://root:password@localhost:3306/mydatabase'
DATABASE_URL = 'mysql://user:pass123@example.com:3306/mydatabase'
DATABASE_URL = 'postgresql://postgres:password@localhost:5432/mydatabase'
DATABASE_URL = 'postgresql://user:pass123@example.com:5432/mydatabase'

import os
db_username = os.getenv('DB_USERNAME')
db_password = os.getenv('DB_PASSWORD')
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')
db_name = os.getenv('DB_NAME')
database_url = f"mysql://{db_username}:{db_password}@{db_host}:{db_port}/{db_name}"
```



### MongoDB
The most widely used typical NoSQL database.      
1. Parameter configuration is as follows:       
```python
#template:
DATABASE_URL = 'mongodb://username:password@hostname:port/'
#examples:
DATABASE_URL = 'mongodb://127.0.0.1:27017/'
DATABASE_URL = 'mongodb://user:pass123@example.com:27017/'
```

2. If mongodb is not installed on the target platform, you can refer to the [official documentation](https://www.mongodb.com/docs/manual/installation/) for installation instructions. Here is the installation method for Ubuntu:   
```bash
sudo apt install gnupg curl
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
   sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg \
   --dearmor
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update
sudo apt install -y mongodb-org
sudo systemctl start mongod
sudo systemctl enable mongod
```



### Redis
A memory NoSQL database that can persist to disk.    
If the target system already has Redis installed and used for task queues, using Redis directly can save the resource consumption of installing other databases.    
However, before using it, relevant Redis persistence configurations should be done to avoid data loss.    
1. Parameter configuration is as follows (the db_number can be omitted, but if it's 0, it's recommended to omit it):   
```python
DATABASE_URL = 'redis://[:password]@hostname:port/db_number'
DATABASE_URL = 'redis://127.0.0.1:6379/0'
DATABASE_URL = 'redis://:password123@example.com:6379/1'
```

2. If Redis is not installed on the target platform, you can refer to the [official documentation](https://redis.io/docs/install/install-redis/) for installation instructions. Here is the installation method for Ubuntu:   
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```



### Pickle
A very simple single-file NoSQL "database" created by the author using Python's pickle data persistence standard library.    
It can be used for resource-constrained systems or for testing purposes.    
The database file path support both absolute path and relative path, with the project directory as the base directory for relative path.   
Parameter configuration is as follows:   
```python
#template:
DATABASE_URL = 'pickle:////path/to/database.db'
#examples:
DATABASE_URL = 'pickle:////C:/Users/name/kindleear/site.db'
DATABASE_URL = 'pickle:////home/username/dbfilename.db'
DATABASE_URL = 'pickle:///dbfilename.db'  #relative path
```




<a id="taskqueue"></a>
## Task Queue and Scheduler Selection
Task queues are used for asynchronously executing tasks such as fetching web content, creating eBooks, sending emails, etc.    
Scheduler tasks are used for periodically checking whether there is a need for pushing notifications, resetting    expired push records, etc.    



### gae
If you want to deploy to Google Cloud, you can only choose GAE.    
```python
TASK_QUEUE_SERVICE = "gae"
TASK_QUEUE_BROKER_URL = ""
```



### apscheduler
Comparatively lightweight, with the simplest configuration, it can work without relying on Redis or other databases by directly using memory to store task states.   
However, there is a risk of losing tasks. If power is lost during the execution of a task, the original task will not rerun after power is restored; it will only wait for the next scheduled time.    
If database persistence is required, it supports SQLite/MySQL/PostgreSQL/MongoDB/Redis, and you can configure it with the same value as DATABASE_URL.    
```python
TASK_QUEUE_SERVICE = "apscheduler"

TASK_QUEUE_BROKER_URL = "memory" # use memory store
# or
TASK_QUEUE_BROKER_URL = "redis://127.0.0.1:6379/"
# or
TASK_QUEUE_BROKER_URL = "sqlite:////home/username/dbfilename.db"
```

Notes:
1. The apscheduler 3.x does not support multi-processes (No matter what job store is used). When used with gunicorn, using multi-threads instead, for example, setting workers=1, threads=3, and disabling preload_app.   



### celery
The most famous task queue, supports various backends such as Redis, MongoDB, SQL, shared directories, etc.     
If database persistence for task states is required, it can be configured with the same value as DATABASE_URL.   
```python
TASK_QUEUE_SERVICE = "celery"

TASK_QUEUE_BROKER_URL = "redis://127.0.0.1:6379/"
# or
TASK_QUEUE_BROKER_URL = "sqlite:////home/username/dbfilename.db"
# or
TASK_QUEUE_BROKER_URL = "file:///var/celery/results/" # results is a directory
TASK_QUEUE_BROKER_URL = "file:////?/C:/Users/name/results/" # keep the prefix 'file:////?/' if in windows
```



### rq
Slightly lighter-weight than Celery, it depends on Redis and requires an additional installation of the Redis service.  
```python
TASK_QUEUE_SERVICE = "celery"
TASK_QUEUE_BROKER_URL = "redis://127.0.0.1:6379/"
```




<a id="sendmail"></a>
## Email Sending Service Selection
To make it more convenient to use and avoid some limitations of free quotas, the email sending service can be configured on the web page after deployment is complete.    
* **GAE**:
Recommended for deployment to Google Cloud, with sufficient quotas and generous email size limit, with a maximum of 31.5MB per email.    

* **SendGrid**:
Recommended for deployment to other platforms, requires additional [registration](https://sendgrid.com/) and application for an API key, with a maximum of 30MB per email.    
Note: I have been unable to register with SendGrid successfully. Regardless of the methods used or the number of email addresses tried, I cannot login to SendGrid. Therefore, I have not personally tested this functionality. If any friends have successfully tested it, please inform me.

* **mailjet**:
You can also use [Mailjet](https://www.mailjet.com/). Just sign up for an account and get your ApiKey and SecretKey. The largest email you can send is 15MB. Don't forget to check that your sender address is on the [Sender addresses](https://app.mailjet.com/account/sender) list before you send any mail.    
During testing, another issue was discovered: if your sender email address is not the one you registered with Mailjet, Mailjet will not report an error; instead, the recipient will never receive the email. Therefore, if sending emails fails with Mailjet, please verify that the sender address is correct.   

* **SMTP**:
This option is flexible, as most email service platforms support SMTP. However, many platforms have various restrictions on SMTP. Before use, please carefully read the relevant instructions, especially considering that the SMTP password for most platforms differs from the regular account password.   

In addition to using existing services available in the market, platforms like Ubuntu also offer convenient ways to deploy your own SMTP service by using postfix.   





<a id="wsgi"></a>
## WSGI container
KindleEar uses the Flask framework to implement web interface management, with the entry point being `main.app` (the app instance object inside the main.py file).      
You can start this app using any web server software that supports the WSGI standard interface.     
For low requirements, you can directly start with the Flask debug server.     
If deploying to Google Cloud, it defaults to using Gunicorn, but you can freely switch to uWSGI, Tornado, mod_wsgi, etc.    
The same applies to other target platforms; choose whichever you prefer or are familiar with.    



<a id="pip"></a>
## requirements.txt
KindleEar uses requirements.txt to manage dependencies on various libraries.     
It allows for easy environment configuration with just one command on various platforms.    
```bash
pip install -r requirements.txt
```

Due to the various configuration combinations, manually configuring requirements.txt can be complex and prone to errors.   
To address this, the author provides a script file `tools/update_req.py`.    
After configuring config.py, simply execute this file to generate requirements.txt.   
Alternatively, you can choose not to use this script and remove all comments in requirements.txt, which installs all dependencies, as it won't take up much space anyway.   



