# KindleEar开发者备忘录

# Docker
## 构建镜像
```bash
#using the pre-created builder, build && push
cd ~/kindleear && \
sudo docker buildx use builder && \
sudo docker buildx build --push --platform=linux/amd64,linux/arm64 -t kindleear/kindleear:latest -t kindleear/kindleear:3.1.0 -f docker/Dockerfile . && \
cd ~
#or, create a new builder, build && push
cd ~/kindleear && \
sudo docker buildx create --use --name=builder && \
sudo docker buildx build --push --platform=linux/amd64,linux/arm64 -t kindleear/kindleear:latest -t kindleear/kindleear:3.1.0 -f docker/Dockerfile . && \
cd ~
#using the pre-created builder, build && output
cd ~/kindleear && \
sudo docker buildx use builder && \
sudo docker buildx build --platform=linux/arm64 -t kindleear/kindleear --output type=docker,dest=../kindleear.tar -f docker/Dockerfile . && \
cd ~
#or, build a single platform image for test
cd ~/kindleear && sudo docker build -t kindleear/kindleear -f docker/Dockerfile . && cd ~
#or, build a single platform image without cache and tag it
sudo docker build --no-cache -t kindleear/kindleear .
sudo docker tag id kindleear/kindleear:version
```

## 常用Docker命令
```bash
sudo docker images
sudo docker rmi id
sudo docker stop name
sudo docker rm name
sudo docker ps -a
sudo docker compose up -d
sudo docker run -d
sudo docker run -it id /bin/bash
sudo docker exec -it container_id sh
sudo docker login
sudo docker push kindleear/kindleear:tag
sudo docker push kindleear/kindleear
sudo docker load -i kindleear.tar
docker buildx ls
docker buildx rm xname
```

# 电子书简要生成流程
  build_ebook.ConvertToEbook() -> plumber.run() -> recipe_input.convert() -> news.BasicNewsRecipe.download()
  plumber.create_oebbook() -> OEBReader.call() -> output_plugin.convert()

# KindleEar额外自带的Python库，这些库不用pip安装，不在requirements.txt里面
* readability-lxml: 修改了其htmls.py|shorten_title()

# 如果要添加新选项，最好添加到 calibre.customize.conversion.py | InputFormatPlugin | common_options, 

# 关于i18n翻译
* javascript的翻译没有采用其他复杂或引入其他依赖的方案，而是简单粗暴的在base.html里面将要翻译的字段预先翻译，
然后保存到一个全局字典对象。
* 文本字符串有修改后，逐个执行几个脚本。
第一个脚本提取文本到messages.pot并将文本更新到messages.po；
手工翻译中文后，执行第二个python脚本，调用AI自动翻译其他语言的po文件；
翻译后使用第三个脚本将po文件编译为mo文件；
```bat
tools\pybabel_extract.bat
tools\pybabel_auto_translate.py
tools\pybabel_compile.bat
```
* 翻译空白字符条目 msgstr ""
* 在po后查找fuzzy，更新翻译后，将fuzzy标识行删除


# Cmder执行run_flask.bat调试环境快捷方式    
```
C:\Windows\Cmder\Cmder.exe /x "/cmd D:\Programer\Project\KindleEar\tools\run_flask.bat"
```


# 申请Let’s Encrypt ssl证书
* sudo apt update && sudo apt install certbot
* sudo certbot certonly --manual --preferred-challenges=dns --email xx@xx.com -d www.yourdomain.com
* 添加txt记录
* 自动续签方案：
1. crontab
```bash
sudo crontab -e
#打开编辑器后添加下面一行
0 0 * * 1 /usr/bin/certbot renew >> /var/log/certbot-renew.log
```

2. systemd
2.1 创建 /etc/systemd/system/certbot-renew.service
```
[Unit]
Description=Renew SSL certificate with certbot
[Service]
Type=oneshot
ExecStart=/usr/bin/certbot renew
ExecStartPost=/bin/cp -f /etc/letsencrypt/live/www.yourdomain.com/privkey.pem /home/ubuntu/data/privkey.pem
ExecStartPost=/bin/cp -f /etc/letsencrypt/live/www.yourdomain.com/fullchain.pem /home/ubuntu/data/fullchain.pem
```

2.2 创建 /etc/systemd/system/certbot-renew.timer
```
[Unit]
Description=Run certbot renew weekly
[Timer]
OnCalendar=Mon *-*-* 00:00:00
Persistent=true
[Install]
WantedBy=timers.target
```
2.3 启用并启动定时器
```bash
sudo systemctl daemon-reload
sudo systemctl enable certbot-renew.timer
sudo systemctl start certbot-renew.timer
```

# 本地环境构建和调试
  1. 安装标准环境google cloud SDK/gloud CLI，并且执行 gcloud init
  2. 安装依赖 `pip install requirements.txt`
  3. 使用命令打开调试环境
     `c:\python38\python.exe "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\dev_appserver.py" --runtime_python_path="python27=c:\python27\python.exe,python3=c:\python38\python.exe"  --skip_sdk_update_check=true app.yaml worker.yaml`
     `--support_datastore_emulator=true`
     dev_appserver.py --runtime_python_path=c:\python38\python.exe --application=kindleear5 app.yaml

  2. 即使在本机，GAE应用也运行在一个沙箱内，无法读写本机文件，如果要突破，可以修改 stubs.py 里面的 FakeFile 类。
     * 删除__init__()
     * is_file_accessible() 无条件返回 FakeFile.Visibility.OK
     * stubs.py默认位置：C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\platform\google_appengine\google\appengine\tools\devappserver2\python\runtime\stubs.py
  3. datastore如果连接不上模拟器，一直使用远端数据库，可以手动修改 site-packages\google\cloud\datastore\client.py
     Client.__init__()，将 emulator_host 修改为 'localhost:8081'

# [google cloud datastore本地模拟器](https://cloud.google.com/datastore/docs/tools/datastore-emulator)
  0. 安装和配置 Java JDK 11+
  1. [获取凭证](https://cloud.google.com/docs/authentication/application-default-credentials)：
     `gcloud auth application-default login` #application-default是gcloud命令的参数名，不用修改
  2. 安装datastore模拟器：`gcloud components install cloud-datastore-emulator`
  3. 设置环境变量（每次启动模拟器服务前都需要重新设置环境变量）
     `gcloud beta emulators datastore env-init > set_vars.cmd && set_vars.cmd`
  4. 启动模拟器服务：`gcloud beta emulators datastore start`
     默认模拟器数据库文件：local_db.bin
  5. 如果需要连接到网络数据库，则需要移除环境变量
     `gcloud beta emulators datastore env-unset > remove_vars.cmd && remove_vars.cmd`
  6. 这个项目 [DSAdmin](https://github.com/remko/dsadmin) 可以本机管理模拟器数据库
     `./dsadmin --project=my-datastore-project --datastore-emulator-host=localhost:8081`

gcloud app deploy cron.yaml
gcloud app deploy queue.yaml
gcloud services list #current enabled services
gcloud services list | grep datastore.googleapis.com
gcloud services enable datastore.googleapis.com
gcloud services enable tasks.googleapis.com
gcloud services enable cloudtasks.googleapis.com
gcloud services enable translate.googleapis.com
gcloud services enable texttospeech.googleapis.com

#all available services
gcloud services list --available > services.txt

# Windows 安装celery
* 安装并启动redis服务，(Windows只能安装redis3 <https://github.com/MicrosoftArchive/redis/releases>)
* 安装celery，如果是Windows，还需要安装 eventlet
   > `pip install celery, redis, eventlet`
* 切换到KindleEar主目录，启动celery服务，main是入口文件的名字: main.py，只有Windows需要参数 '-P eventlet'，需要cmd最大化可以先输入wmic再quit即可
   > `celery -A main.celery_app worker --loglevel=info --concurrency=2 -P eventlet`
* celery命令：
   > `redis-cli.exe -p 6379`
   > `KEYS *`

# Windows 安装配置 MongoDB
* 下载安装(注意安装时要取消mongodb compass)，创建一个目录保存数据库文件，比如 c:\mongodb\db和c:\mongodb\log
* 安装启动服务
  >`"C:\Program Files\MongoDB\Server\3.6\bin\mongod.exe" --dbpath "c:\mongodb\db" --logpath "c:\mongodb\log\MongoDB.log" --install --serviceName "MongoDB"  --journal`
  > `net start MongoDB`
  > `"C:\Program Files\MongoDB\Server\3.6\bin\mongo.exe"`
  > `db.Book.insert({"name":"1001 nights"})`
  > `db.Book.find()`
* 其他命令
  > `net stop MongoDB`  #停止后台服务
  > `mongod.exe --remove`  #删除后台服务`


# Python托管平台的一些了解
* [appengine](https://cloud.google.com)：必须绑定信用卡，但有免费额度，有收发邮件服务，任务队列，后台进程
* [Heroku](https://www.heroku.com): 没有免费额度，入门套餐也需要付费
* [Pythonanywhere](https://www.pythonanywhere.com): 有免费计划，不支持任务队列，有每天两次的预定任务计划
* [Adaptable](https://adaptable.io): 免费计划不支持任何形式的任务队列和后台任务，5分钟内必须完成应答请求
* [render](https://render.com): 有免费计划，没有免费cron额度



# 常用链接
[App Engine 文档](https://cloud.google.com/appengine/docs)
[yaml配置文档](https://cloud.google.com/appengine/docs/standard/reference/app-yaml?tab=python)
[Cloud Tasks]https://cloud.google.com/tasks/docs
[Adding your favorite news website](https://manual.calibre-ebook.com/news.html)
[GAE限额](https://cloud.google.com/appengine/docs/standard/quotas)
[查看GAE日志当前存储量](https://console.cloud.google.com/logs/storage)

