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
在同一个页面的右上角有一个图标 "激活 Cloud shell"， 点击它，打开 cloud shell， 拷贝粘贴以下命令（**请保持多行命令格式**），根据提示不停的按 "y" 即可完成部署。    
部署和更新都使用同样一条命令。     

```bash
rm -rf kindleear && \
git clone --depth 1 https://github.com/cdhigh/kindleear.git && \
chmod +x kindleear/tools/gae_deploy.sh && \
kindleear/tools/gae_deploy.sh
```

**注1：** 默认配置为B2实例，1个工作进程，2个工作线程，20分钟超时，如果需要其他配置，可以修改最后一行代码   

```bash
#instance_class: B1 (384MB/600MHz)
#max_instances: 1
#threads: 2 (2 thread per instance)
#idle_timeout: 15m (minutes)
kindleear/tools/gae_deploy.sh B1,1,t2,15m
```

**注2：** 如果想精简内置Recipe文件，仅保留你需要的语种，可以在 `kindleear/tools/gae_deploy.sh` 命令前增加一行。
假如内置的Recipe你一个都不想要，可以直接删除 `application/recipes/*.xml, *.zip`。      

```bash
# Modify the list after trim_recipes.py to keep desired languages.
rm -rf kindleear && \
git clone --depth 1 https://github.com/cdhigh/kindleear.git && \
chmod +x kindleear/tools/gae_deploy.sh && \
python kindleear/tools/trim_recipes.py en,zh && \
kindleear/tools/gae_deploy.sh B1,1,t2,15m
```

3. 如需要GAE部署的更多信息，请参考 [其他说明](#gae_other_instructions) 章节，比如怎么解决 "Unauthorized sender" 错误等。    



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
gcloud beta app deploy --version=1 app.yaml worker.yaml
gcloud beta app deploy --version=1 cron.yaml
gcloud beta app deploy --version=1 queue.yaml
gcloud beta app deploy --version=1 dispatch.yaml
```

3. 版本更新，只需要执行一行代码即可

```bash
gcloud beta app deploy --version=1 app.yaml worker.yaml
```


<a id="gae_other_instructions"></a>
### 其他说明    
1. 初始账号和密码为 admin/admin。
2. 部署时出现下面的几个提示时记得按 y，因为光标自动下移到了下一行，往往会忘记按 y，否则会一直卡在这里。  
```
Updating config [cron]...API [cloudscheduler.googleapis.com] not enabled on project [xxx]. Would you like to enable and retry (this will take a few minutes)
Updating config [queue]...API [cloudtasks.googleapis.com] not enabled on project [xxx]. Would you like to enable and retry (this will take a few minutes)
```

3. 如果出现部署失败并且多次尝试后仍然无法解决，比如"Timed out fetching pod."之类的错误，可以关停此id，然后重建一个，部署时选择其他区域。   

4. 部署成功后先到 [GAE后台](https://console.cloud.google.com/appengine/settings/emailsenders) 将你的发件地址添加到 "Mail API Authorized Senders"，否则投递会出现 "Unauthorized sender" 错误。

5. 如果你之前已经部署过Python2版本的KindleEar，建议新建一个项目来部署Python3版本，因GAE不再支持Python2部署，所以覆盖后无法恢复原先的版本。   

6. GAE的计算资源是可伸缩配置的，一般情况下，只有后台实例(worker.yaml)需要修改，默认为B2(768MB/1.2GHz)，根据你的推送量调整这个配置，如果推送量大，调整为B4，如果推送量小，缩小为B1。额外的，如果后台出现 " [CRITICAL] WORKER TIMEOUT"，则需要增加 entrypoint 里面的 --timeout 参数。       

7. 出现各种问题后，随时可以到 [后台](https://console.cloud.google.com/logs) 查看log记录，根据错误信息来逐一解决。   



<a id="docker"></a>
## Docker (VPS)
Docker是什么？如果你不了解，就把它类比为Windows平台的绿色软件的增强版。   
Docker不限平台，只要目标平台支持Docker，资源足够就可以部署。   

1. [安装Docker](https://docs.docker.com/engine/install/) （已安装则跳过）
每个平台的安装方法不一样，KindleEar提供了一个ubuntu的脚本。   

```bash
wget -O - https://raw.githubusercontent.com/cdhigh/KindleEar/master/docker/ubuntu_docker.sh | bash
```

2. 安装完Docker后，执行以下命令就可以让服务运行起来（`http://example.com` 修改为你自己的值）。  

```bash
wget https://raw.githubusercontent.com/cdhigh/KindleEar/master/docker/ke-docker.sh
chmod +x ke-docker.sh
ke-docker.sh http://example.com
```

注1：KindleEar更新后，重新执行最后一行命令可以自动拉取并启动更新后的版本。    
注2：脚本会在当前目录创建data子目录（如果不存在）。      
注3：如果需要https支持，将 fullchain.pem/privkey.pem 拷贝到data目录，再执行此命令。   
注4：默认镜像的配置：    
* sqlite数据库    
* apscheduler，内存队列   
* 数据库文件和log文件保存到同一目录 /data   
如果你需要使用其他数据库或任务队列，可以使用Dockerfile直接构建镜像。   
特别是如果你需要启用多进程，则必须将内存队列更换为redis或其他，同时要修改gunicorn.conf.py或default.conf。     


如果连不上，请确认80/443端口是否已经开放，不同的平台开放80/443端口的方法不一样，可能为iptables或ufw。
比如：

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 7 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

或者开放所有端口   
```bash
sudo iptables -P INPUT ACCEPT
sudo iptables -P FORWARD ACCEPT
sudo iptables -P OUTPUT ACCEPT
sudo iptables -F
```

3. 如果需要入站邮件功能（需要开放25端口），请使用docker-compose。     

3.1 推荐使用Caddy做为web服务器，可以自动申请和续期SSL证书（一定要先正确填写DOMAIN）    

```bash
mkdir data #for database and logs
wget https://raw.githubusercontent.com/cdhigh/KindleEar/master/docker/docker-compose.yml
wget https://raw.githubusercontent.com/cdhigh/KindleEar/master/docker/Caddyfile

#important!!!  Change the environ variables APP_DOMAIN/DOMAIN
vim ./docker-compose.yml

sudo docker compose up -d
```

3.2 如果更喜欢Nginx    

```bash
mkdir data #for database and logs
wget https://raw.githubusercontent.com/cdhigh/KindleEar/master/docker/docker-compose-nginx.yml
wget https://raw.githubusercontent.com/cdhigh/KindleEar/master/docker/default.conf

#Change the environ variables APP_DOMAIN/DOMAIN
vim ./docker-compose-nginx.yml

sudo docker compose -f docker-compose-nginx.yml up -d
```

使用Nginx时如果需要https，预先将ssl证书 fullchain.pem/privkey.pem 拷贝到data目录，取消default.conf/docker-compose-nginx.yml里面对应的注释即可。      

4. 使用docker-compose的版本更新方法      

```bash
sudo docker compose pull
sudo docker compose up -d --remove-orphans
sudo docker image prune
```


5. 需要查询日志文件

```bash
tail -n 100 ./data/gunicorn.error.log
tail -n 100 ./data/gunicorn.access.log
```

6. 如果不喜欢每次输入docker都使用sudo，可以将你的账号添加到docker用户组

```bash
sudo usermod -aG docker your-username
```



<a id="synology"></a>
## 群晖 (NAS)
1. 打开 "套件中心"，搜索并安装Docker。
2. 打开Docker (Container Manager)，在注册表搜索 "KindleEar"，安装 kindleear/kindleear。
3. 运行KindleEar，进入设置界面：
  3.1 第一步勾选"启用自动重新启动"；
  3.2 第二步：
    3.2.1 在"端口设置"里面选择一个本地端口(比如:8001)映射到KindleEar的8000端口
    3.2.2 在"存储空间设置"里面添加一个文件夹映射到 `/data`，比如 `/docker/data` 映射到 `/data`，权限为"读取/写入"
4. 启动完成后使用 http://ip:8001 访问。  
5. 如果需要链接分享功能，可以设置环境变量 `APP_DOMAIN`。 


<a id="oracle-cloud"></a>
## Oracle cloud (VPS)
这是手动在一个 [Oracle VPS](https://cloud.oracle.com/) 上部署的步骤，比较复杂，一般不建议，如果没有特殊要求，推荐使用docker镜像。   
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
创建完成后在"实例信息"点击"子网"链接，在"安全列表"中修改或创建入站规则，将TCP的端口删除，ICMP的类型和代码删除，
只保留一个入站规则：
源类型：CIDR
源CIDR：0.0.0.0/0
IP协议：所有协议

然后测试ping对应的IP，能ping通说明实例配置完成。    

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
python3 ./tools/update_req.py docker #update requirements.txt

source ./venv/bin/activate  #activate virtual environ
pip install -r requirements.txt #install dependencies
python3 ./main.py db create #create database tables

#open port 80/443
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 7 -m state --state NEW -p tcp --dport 443 -j ACCEPT
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


