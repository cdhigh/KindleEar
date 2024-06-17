---
sort: 3
---
# Deployment
KindleEar supports deployment on multiple platforms. I will only list some platforms that I have tested here. You are welcome to add deployment guides for other platforms.   
Here is a list of platforms that can be used permanently for free, excluding those that require payment such as Heroku, and also excluding platforms like Azure/AWS that only offer a free trial for a limited time.   
This GitHub repository [heroku-free-alternatives](https://github.com/anandrmedia/heroku-free-alternatives) lists some platforms similar to Heroku. If you're interested, you can try them out yourself.   



<a id="gae"></a>
## Google Cloud (PaaS)

### Direct cloud shell deployment method (Recommended)
1. Create a project   
Open [google cloud](https://console.cloud.google.com/appengine) and create a new project.    

2. Shell deployment   
On the same page, in the top right corner, there is an icon labeled "Activate Cloud Shell". Click on it to open the cloud shell. Copy and paste the following commands (**Please keep the multi-line format**), and follow the prompts by pressing "y" continuously to complete the deployment.   
Deployment and updating are both done with the same command.     

```bash
rm -rf kindleear && \
git clone --depth 1 https://github.com/cdhigh/kindleear.git && \
chmod +x kindleear/tools/gae_deploy.sh && \
kindleear/tools/gae_deploy.sh
```

**Note 1:** The default configuration is B2 instance, 1 worker process, 2 worker threads, and a 20-minute timeout. If you need a different configuration, you can modify the last line of code, for example:  

```bash
#instance_class: B1 (384MB/600MHz)
#max_instances: 1
#threads: 2 (2 thread per instance)
#idle_timeout: 15m (minutes)
kindleear/tools/gae_deploy.sh B1,1,t2,15m
```

**Note 2:** If you want to trim the built-in Recipe file to keep only the languages you need, you can add a line before the `kindleear/tools/gae_deploy.sh` command.    
If you don't want any of the built-in recipes, you can directly delete `application/recipes/*.xml, *.zip`.

```bash
# Modify the list after trim_recipes.py to keep desired languages.
rm -rf kindleear && \
git clone --depth 1 https://github.com/cdhigh/kindleear.git && \
chmod +x kindleear/tools/gae_deploy.sh && \
python kindleear/tools/trim_recipes.py en,zh && \
kindleear/tools/gae_deploy.sh B1,1,t2,15m
```

3. Refer to the [Other Instructions](#gae_other_instructions) section for additional information, such as troubleshooting the 'Unauthorized sender' issue.    



### Local GLI Command Deployment Method

1. Download the latest version of KindleEar from the GitHub page. In the bottom right corner of the page, there's a button labeled "Download ZIP". Clicking it will download a ZIP document containing all the source code. Then, unzip it to a directory of your choice, such as D:\KindleEar.   

2. Install [gloud CLI](https://cloud.google.com/sdk/docs/install), and then execute: 

```bash
gcloud components install app-engine-python app-engine-python-extras # Run as Administrator
gcloud init
gcloud auth login
gcloud auth application-default set-quota-project your_app_id
gcloud config set project your_app_id
python kindleear/tools/update_req.py gae
gcloud beta app deploy --version=1 app.yaml worker.yaml
gcloud beta app deploy --version=1 cron.yaml
gcloud beta app deploy --version=1 queue.yaml
gcloud beta app deploy --version=1 dispatch.yaml
```

3. For version updates, simply execute one line of code:  

```bash
gcloud beta app deploy --version=1 app.yaml worker.yaml
```

<a id="gae_other_instructions"></a>
### Other Instructions
1. The initial username and password are admin/admin.   

2. When prompted during deployment with the following messages, remember to press "y". The cursor automatically moves to the next line, and it's easy to forget to press "y". Otherwise, it will remain stuck at this step.    

```
Updating config [cron]...API [cloudscheduler.googleapis.com] not enabled on project [xxx]. Would you like to enable and retry (this will take a few minutes)
Updating config [queue]...API [cloudtasks.googleapis.com] not enabled on project [xxx]. Would you like to enable and retry (this will take a few minutes)
```  


3. If encountering errors like "Timed out fetching pod", you have the option to delete this app id, recreate a new one and select a different region during deployment.    

4. After successful deployment, go to the [GAE console](https://console.cloud.google.com/appengine/settings/emailsenders) and add your sender address to "Mail API Authorized Senders" to prevent "Unauthorized sender" errors during delivery.     

5. If you have previously deployed Python2 version of KindleEar, it is advisable to create a new project to deploy the Python3 version. Since GAE no longer supports Python 2 deployment, reverting to the original version after overwriting is not possible.     

6. GAE's resources are scalable. Generally, only backend instances (worker.yaml) need to be customized. The default configuration is B2(768MB/1.2GHz). Adjust this configuration based on your RSS volume: increase to B4 for larger volumes and decrease to B1 for smaller volumes. Additionally, if the logs shows a '[CRITICAL] WORKER TIMEOUT' error, it requires increasing the '--timeout' parameter within the entrypoint section.    

7. If various issues arise, you can always check the [logs](https://console.cloud.google.com/logs) resolve them one by one based on the error messages.    




<a id="docker"></a>
## Docker (VPS)
What is Docker? just think of it as an enhanced version of portable software.   

1. [Install Docker](https://docs.docker.com/engine/install/) (Skip if already installed)    
Installation methods vary for each platform. KindleEar provides a script for Ubuntu.   

```bash
wget -O - https://raw.githubusercontent.com/cdhigh/KindleEar/master/docker/ubuntu_docker.sh | bash
```


2. After installing Docker, run the following commands to get the service running (replace `http://example.com` with your own value).     

```bash
wget https://raw.githubusercontent.com/cdhigh/KindleEar/master/docker/ke-docker.sh
chmod +x ke-docker.sh
ke-docker.sh http://example.com
```

**Note 1:** After KindleEar updates, rerun the last command to automatically pull and start the updated version.    
**Note 2:** The script will create a `data` subdirectory in the current directory (if it doesn't already exist).    
**Note 3:** If you need HTTPS support, copy `fullchain.pem` and `privkey.pem` to the `data` directory, then run the command again.    
**Note 4:** Default image configuration:    
* SQLite database    
* APScheduler with memory jobstore    
* Database files and log files are saved to the same directory `/data`    
If you need to use another database or task queue, you can build the image directly using the Dockerfile.    
Especially if you need to enable multiple processes, you must replace the memory jobstore with Redis or another option, and modify `gunicorn.conf.py` or `default.conf`.    

If unable to connect, ensure port 80/443 is open. Methods to open port 80/443 vary across platforms, such as iptables or ufw.     
For example:    

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 7 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

or allow all ports:   
```bash
sudo iptables -P INPUT ACCEPT
sudo iptables -P FORWARD ACCEPT
sudo iptables -P OUTPUT ACCEPT
sudo iptables -F
```

3. If you need inbound email functionality (requiring port 25 to be open), please use docker-compose.    

3.1 Using Caddy as the web server is recommended, as it can automatically request and renew SSL certificates.       

```bash
mkdir data #for database and logs
wget https://raw.githubusercontent.com/cdhigh/KindleEar/master/docker/docker-compose.yml
wget https://raw.githubusercontent.com/cdhigh/KindleEar/master/docker/Caddyfile

#important!!!  Change the environ variables APP_DOMAIN/DOMAIN
vim ./docker-compose.yml

sudo docker compose up -d
```

3.2 If you perfer Nginx.    

```bash
mkdir data #for database and logs
wget https://raw.githubusercontent.com/cdhigh/KindleEar/master/docker/docker-compose-nginx.yml
wget https://raw.githubusercontent.com/cdhigh/KindleEar/master/docker/default.conf

# Change the environment variables APP_DOMAIN/DOMAIN
vim ./docker-compose-nginx.yml

sudo docker compose -f docker-compose-nignx.yml up -d
```

If HTTPS for Nginx is needed, copy the SSL certificate fullchain.pem/privkey.pem to the data directory, and uncomment the corresponding lines in default.conf/docker-compose-nginx.yml.   


4. Method for Updating Using Docker Compose     

```bash
sudo docker compose pull
sudo docker compose up -d --remove-orphans
sudo docker image prune
```


5. To check log files

```bash
tail -n 100 ./data/gunicorn.error.log
tail -n 100 ./data/gunicorn.access.log
```


6. If you don't like using 'sudo' every time you use Docker, you can add your account to the 'docker' user group.    

```bash
sudo usermod -aG docker your-username
```



<a id="synology"></a>
## Synology (NAS)
1. Open the "Package Center", search for and install Docker.
2. Open Docker (Container Manager), search for "KindleEar" in tab "Registry", and install "kindleear/kindleear".
3. Run KindleEar and show the settings ui:
   3.1. First, check "Enable auto-restart";
   3.2. Second:
      3.2.1. In the "Port Settings", select a local port (eg. 8001) to map to KindleEar's 8000 port;
      3.2.2. In the "Volume Settings", add a folder mapped to `/data`, for example, map `/docker/data` to `/data`, with "Read/Write" permissions.
4. After starting, access it via http://ip:8001.
5. If you need the link sharing feature, you can set the environment variable `APP_DOMAIN`.   


<a id="oracle-cloud"></a>
## Oracle cloud (VPS)   
These are manual deployment steps on [Oracle VPS](https://cloud.oracle.com/) , which can be quite complex. Generally, it's not recommended.     
If there are no specific requirements, it's advisable to use Docker images instead.    

1. config.py Key Parameter Example

```python
DATABASE_URL = "sqlite:////home/ubuntu/site/kindleear/database.db"
TASK_QUEUE_SERVICE = "apscheduler"
TASK_QUEUE_BROKER_URL = "redis://127.0.0.1:6379/"
KE_TEMP_DIR = "/tmp"
DOWNLOAD_THREAD_NUM = "3"
```

2. Create a compute instance, with the recommended configuration being "Always Free".  
Choose an image that you are familiar with, I selected Ubuntu minimal.   
Remember to download and save the private ssh key. Once created, click on the "Subnet" link on "Instance Details" page then modify or create inbound rules in the "Security Lists" by removing TCP ports and ICMP types and codes.   
Keep only one Ingress Rule:     
Source Type: CIDR         
Source CIDR: 0.0.0.0/0           
IP Protocol: All protocols          

Test ping the corresponding IP, if successful, it indicates that the instance configuration is complete.   

3. Connect remotely to the instance using your preferred SSH tool.   
3.1 If using puTTY, first convert the ssh private key to ppk format using puttyGen. 
Open puTTY, the Host format as username@IP, port 22. You can find the username in the "Instance Details" page. Import the private key file under Connection|SSH|Auth|Credentials.  
3.2 If using Xshell, choose "Public Key" for authentication method and import the previously saved private key file.  

4. Upon login, it is recommended to first change the root password.  

```bash
sudo -i
passwd
```


5. Talk is cheap, show me commands.   

```bash
sudo apt update
sudo apt upgrade
sudo apt install nginx
sudo apt install git python3.10 python3-pip
sudo pip3 install virtualenv
sudo apt install redis-server
sudo systemctl start nginx
sudo systemctl start redis-server
sudo systemctl enable nginx
sudo systemctl enable redis-server

curl localhost #test if nginx works well

sudo apt install vim-common
mkdir ~/site
mkdir ~/log
cd ~/site

#fetch code from github, or you can upload code files by xftp/scp
git clone https://github.com/cdhigh/kindleear.git
chmod -R 775 ~    #nginx user www-data read static resource
cd kindleear
virtualenv --python=python3 venv  #create virtual environ
vim ./config.py  #start to modify some config items
python3 ./tools/update_req.py docker #update requirements.txt

source ./venv/bin/activate  #activate virtual environ
pip install -r requirements.txt #install dependencies
python3 ./main.py db create #create database tables

#open port 80/443
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 7 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save

#modify nginx configuration
#1. change the first line to 'user loginname;', for example 'user ubuntu;'
#2. add a line 'client_max_body_size 16M;' to http section
sudo vim /etc/nginx/nginx.conf
vim ./tools/nginx/nginx_default  #change server_name if you want
sudo cp -rf ./tools/nginx/nginx_default /etc/nginx/sites-enabled/default
sudo nginx -t #test if nginx config file is correct

#set gunicorn auto start
sudo cp ./tools/nginx/gunicorn.service /usr/lib/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl start gunicorn
sudo systemctl status gunicorn
sudo systemctl enable gunicorn

sudo systemctl restart nginx
sudo systemctl status nginx
```

6. Version Update Method

```bash
# First, update the code using git/ftp/scp, etc. Ensure to preserve the database files.
sudo systemctl restart gunicorn
sudo systemctl status gunicorn  # Confirm it is running
```

7. Now you can use "http://ip" in your browser to confirm if the deployment was successful. If you have a SSL certificate, you can also proceed to configure Nginx to use SSL.
If you already have a domain name, you can bind it to your instance. If not, you can easily apply for one from a free domain registrar like [FreeDomain.One](https://freedomain.one/) or [Freenom](https://www.freenom.com/) etc. I applied for a domain name at FreeDomain.One, which was very simple. After successfully applying, you just need to enter the IP address of your Oracle Cloud instance on the page, without any complicated configurations.   

8. To check for errors, use the following commands to query the backend logs:   

```bash
cat /var/log/nginx/error.log | tail -n 100
cat /home/ubuntu/log/gunicorn.error.log | tail -n 100
cat /home/ubuntu/log/gunicorn.access.log | tail -n 100
```

9. Epilogue: If you choose Oracle Cloud, it is recommended to enable their "OCI Email Delivery" service and utilize SMTP for sending emails. This service supports single email up to 60MB, which I have yet to find supported by any other service provider.   





<a id="pythonany-where"></a>
## PythonAnywhere (PaaS)
1. config.py Key Parameter Example

```python
DATABASE_URL = "mysql://name:pass@name.mysql.pythonanywhere-services.com/name$default"
TASK_QUEUE_SERVICE = ""
TASK_QUEUE_BROKER_URL = ""
```

2. Log in to [PythonAnywhere](https://www.pythonanywhere.com), go to the "Web" tab, click "Add a new web app" on the left, and create a Flask application.   

3. Go to the "Databases" tab, initialize mysql and create a database.   

4. Refer to the [UploadingAndDownloadingFiles](https://help.pythonanywhere.com/pages/UploadingAndDownloadingFiles) documentation to upload the code using the git or zip method.    

5. Open a Bash console in the "Files" tab and execute the bash command `pip install -r requirements.txt`.   
6. Create a scheduled task. PythonAnywhere does not support setting scheduled tasks freely in the code, and free users can only set one scheduled task, which is a big limitation. However, if you want to try it, you can go to the "Tasks" tab and create a Task according to the time you want to push the subscription. The bash command is:
`python /home/yourname/yourdirectory/main.py deliver now`

If deployed on PythonAnywhere, the delivery time setting on the web page is invalid, and the delivery time is the time of this Task.   

7. If you are a free user, you need to log in to PythonAnywhere at least once every three months and click "Run until 3 months from today". Otherwise, your application will be suspended.   

**Note:** After testing, it is not suitable for our application deployment unless paid, because it has many restrictions. The most fatal restriction is that it implements a whitelist for websites that free users can access. Websites not in its [list](https://www.pythonanywhere.com/whitelist/) cannot be accessed.    

