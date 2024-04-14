---
sort: 3
---
# 部署方法
KindleEar支持多种平台部署，我只在这里列出一些我测试通过的平台，欢迎补充其他平台的部署方法。   
这里列出的平台都是可以永久免费使用的，不包含需要收费的比如heroku等，也不包括只能免费体验一段时间的平台比Azure/AWS等。   
这个github仓库 [heroku-free-alternatives](https://github.com/anandrmedia/heroku-free-alternatives) 里面列出一些类似heroku的平台，如果感兴趣的话，可以自己去尝试。  


<a id="gae"></a>
## google cloud (PaaS)

### 直接云端Shell部署方法(推荐)
1.  创建项目     
打开 [google cloud](https://console.cloud.google.com/appengine) ，创建一个项目。

2. Shell部署    
在同一个页面的右上角有一个图标 "激活 Cloud shell"， 点击它，打开 cloud shell， 拷贝粘贴以下命令，根据提示不停的按 "y" 即可完成部署。
```bash
git clone --depth 1 https://github.com/cdhigh/kindleear.git && \
chmod +x kindleear/tools/gae_deploy.sh && \
kindleear/tools/gae_deploy.sh
```

3. 部署后动作    
部署完成后稍等几分钟等GAE后台创建各种资源。如果还不行，根据后台log错误记录手动去使能各种API。    
比如，可能需要手动使能 [Cloud Datastore API
](https://console.cloud.google.com/apis/library/datastore.googleapis.com) 。    


### 本地GLI命令部署方法
1. github页面上下载KindleEar的最新版本，在页面的右下角有一个按钮"Download ZIP"，点击即可下载一个包含全部源码的ZIP文档，然后解压到你喜欢的目录，比如D:\KindleEar。   

2. 安装 [gloud CLI](https://cloud.google.com/sdk/docs/install)，并且执行 
```bash
gcloud components install app-engine-python app-engine-python-extras # Run as Administrator
gcloud init
gcloud auth login
gcloud auth application-default set-quota-project your_app_id
gcloud config set project your_app_id
python kindleear/tools/update_req.py gae
gcloud beta app deploy --version=1 app.yaml
gcloud beta app deploy --version=1 cron.yaml
gcloud beta app deploy --version=1 queue.yaml
```

3. 版本更新，只需要执行一行代码即可
```bash
gcloud beta app deploy --version=1 app.yaml
```

### 其他说明    
1. 初始账号和密码为 admin/admin。
2. 部署时出现下面的几个提示时记得按 y，因为光标自动下移到了下一行，往往会忘记按 y，否则会一直卡在这里。    
```bash
Updating config [cron]...API [cloudscheduler.googleapis.com] not enabled on project [xxx]. Would you like to enable and retry (this will take a few minutes)? 

Updating config [queue]...API [cloudtasks.googleapis.com] not enabled on project [xxx]. Would you like to enable and retry (this will take a few minutes)?
```

3. 如果出现部署失败并且多次尝试后仍然无法解决，比如"Timed out fetching pod."之类的错误，可以关停此id，然后重建一个，部署时选择其他区域。   

4. 部署成功后先到 [GAE后台](https://console.cloud.google.com/appengine/settings/emailsenders) 将你的发件地址添加到 "Mail API Authorized Senders"，否则投递会出现 "Unauthorized sender" 错误。

5. 如果你之前已经部署过Python2版本的KindleEar，建议新建一个项目来部署Python3版本，因GAE不再支持Python2部署，所以覆盖后无法恢复原先的版本。   

6. 出现各种问题后，随时可以到 [后台](https://console.cloud.google.com/logs) 查看log记录，根据错误信息来逐一解决。   



<a id="docker"></a>
## Docker (VPS)
Docker是什么？如果你不了解，就把它类比为Windows平台的绿色软件的增强版。   
Docker不限平台，只要目标平台支持Docker，资源足够就可以部署。   

1. [安装Docker](https://docs.docker.com/engine/install/) （已安装则跳过）
每个平台的安装方法不一样，KindleEar提供了一个ubuntu的脚本。   
```bash
wget -O - https://raw.githubusercontent.com/cdhigh/KindleEar/master/docker/ubuntu_docker.sh | bash
```

2. 安装完Docker后，执行一条命令就可以让服务运行起来（yourdomain修改为你自己的值）。  
命令执行后就使用浏览器 http://ip 确认服务是否正常运行。   
因为使用了 restart 参数，所以系统重启后会自动重启此服务。    
注：这条命令采用默认配置：    
* sqlite数据库    
* apscheduler，内存队列   
* 数据库文件和log文件保存到同一目录 /data   
如果你需要其他配置组合，根据config.py的变量名传入对应的环境变量即可(-e 参数)。   

```bash
mkdir data #for database and logs, you can use any folder (change ./data to your folder)
sudo docker run -d -p 80:8000 -v ./data:/data --restart always -e APP_DOMAIN=yourdomain kindleear/kindleear
```

如果连不上，请确认80端口是否已经开放，不同的平台开放80端口的方法不一样，可能为iptables或ufw。
比如：
```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

3. 上面的命令直接使用gunicorn为web服务器，尽管对于我们的应用来说，绰绰有余，而且还能省点资源。      
但是你感觉有些不专业，希望使用更强大的nginx，并且也想启用邮件中转功能（需要开放25端口并且申请域名）：  

```bash
mkdir data #for database and logs
wget https://raw.githubusercontent.com/cdhigh/KindleEar/master/docker/docker-compose.yml
wget https://raw.githubusercontent.com/cdhigh/KindleEar/master/docker/default.conf

#Change the environ variables APP_ID/APP_DOMAIN
#If the email feature is needed, uncomment the section mailglove and change the DOMAIN.
vim ./docker-compose.yml

sudo docker compose up -d
```

4. 需要查询日志文件
```bash
tail -n 100 ./data/gunicorn.error.log
tail -n 100 ./data/gunicorn.access.log
```



<a id="oracle-cloud"></a>
## Oracle cloud (VPS)
这是手动在一个VPS上部署的步骤，比较复杂，一般不建议，如果没有特殊要求，推荐使用docker镜像。   
1. config.py关键参数样例
```python
DATABASE_URL = "sqlite:////home/ubuntu/site/kindleear/database.db"
TASK_QUEUE_SERVICE = "apscheduler"
TASK_QUEUE_BROKER_URL = "redis://127.0.0.1:6379/"
KE_TEMP_DIR = "/tmp"
DOWNLOAD_THREAD_NUM = "3"
```

2. 创建一个计算实例，选择的配置建议"符合始终免费条件"，镜像选择自己熟悉的，我选择的是ubuntu minimal。    
记得下载和保存私钥。    
创建完成后在"实例信息"点击"子网"链接，在"安全列表"中修改或创建入站规则，将TCP的端口删除，ICMP的类型和代码删除，然后测试ping对应的IP，能ping通说明实例配置完成。    

3. 使用自己喜欢的SSH工具远程连接对应IP。
3.1 如果使用puTTY，需要先使用puttyGen将key格式的私钥转换为ppk格式。
打开puTTY，Host格式为username@IP，端口号22，用户名在"实例信息"中可以找到，在Connection|SSH|Auth|Credentials导入私钥文件。   
3.2 如果使用Xshell，身份验证选择Public Key，并导入之前保存的私钥文件。

4. 登录进去后建议先修改root密码
```bash
sudo -i
passwd
```


5. 然后就是命令行时间
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
mkdir -p ~/site
cd ~/site

#fetch code from github, or you can upload code files by xftp/scp
git clone --depth 1 https://github.com/cdhigh/kindleear.git
chmod -R 775 ~    #nginx user www-data read static resource
sudo usermod -aG ubuntu www-data #or add nginx www-data to my group ubuntu
cd kindleear
virtualenv --python=python3 venv  #create virtual environ
vim ./config.py  #start to modify some config items
python3 ./tools/update_req.py #update requirements.txt

source ./venv/bin/activate  #activate virtual environ
pip install -r requirements.txt #install dependencies
python3 ./main.py db create #create database tables

#open port 80/443
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save

mkdir -p /var/log/gunicorn/
chown ubuntu:ubuntu /var/log/gunicorn/ #current user have right to write log
sudo cp ./tools/nginx/gunicorn_logrotate /etc/logrotate.d/gunicorn #auto split log file

#modify nginx configuration
vim ./tools/nginx/nginx_default  #optional, change server_name if you want
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

6. 版本更新方法
```bash
#先更新代码，不管是git/ftp/scp等，注意要保留数据库文件
sudo systemctl restart gunicorn
sudo systemctl status gunicorn  #确认running
```

7. 现在你就可以在浏览器中使用 "http://ip" 来确认是否已经部署成功。如果有证书的话，也可以继续配置nginx来使用SSL。   
如果已有域名，也可以绑定自己的域名，没有的话，随便找一个免费域名注册商申请一个就好，比如 [FreeDomain.One](https://freedomain.one/) 或 [freenom](https://www.freenom.com/) 等，我就在 FreeDomain.One 申请了一个域名，特别简单，在申请成功后的页面直接填入Oracle cloud的instance对应的IP就行，没有复杂的配置。    

8. 出现错误后，查询后台log的命令
```bash
tail -n 100 /var/log/nginx/error.log
tail -n 100 /var/log/gunicorn/error.log
tail -n 100 /var/log/gunicorn/access.log
```

9. 后语，如果部署在Oracle cloud，建议开启其"OCI Email Delivery"服务，然后使用SMTP发送邮件，单邮件最大支持60MB，我还没有发现有哪家服务商能支持那么大的邮件。  



<a id="python-anywhere"></a>
## PythonAnywhere (PaaS)
1. config.py关键参数样例
```python
DATABASE_URL = "mysql://name:pass@name.mysql.pythonanywhere-services.com/name$default"
TASK_QUEUE_SERVICE = ""
TASK_QUEUE_BROKER_URL = ""
```

2. 登录 [pythonanywhere](https://www.pythonanywhere.com)，转到 "Web" 选项卡，点击左侧 "Add a new web app"，创建一个Flask应用。   

3. 转到 "Databases" 选项卡，初始化mysql并创建一个数据库。    

4. 参考 [UploadingAndDownloadingFiles](https://help.pythonanywhere.com/pages/UploadingAndDownloadingFiles) 文档，使用git或zip方法上传代码。   
5. 在 "Files" 选项卡打开一个 Bash console，执行bash命令 `pip install -r requirements.txt`    

6. 创建定时任务。PythonAnywhere不支持代码中自由设置定时任务，并且免费用户只能设置一个定时时间，限制较大，不过如果要勉强使用，可以到 "Tasks" 选项卡，根据你希望推送订阅的时间创建一个Task，命令行为：
`python /home/yourname/yourdirectory/main.py deliver now`
如果部署在PythonAnywhere，则网页上的投递时间设置无效，投递时间就是这个Task的执行时间。   

7. 如果你是免费用户，需要至少每三个月登录一次pythonanywhere，点击一次 "Run until 3 months from today"，否则你的应用就会被暂停。   

注：经过测试，除非付费，否则PythonAnywhere不适合我们的应用部署，因为其限制较多，最致命的限制就是其对免费用户能访问的网站实施白名单措施，不在其 [列表中的网站](https://www.pythonanywhere.com/whitelist/) 无法访问。


