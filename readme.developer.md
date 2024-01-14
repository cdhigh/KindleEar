# KindleEar面向开发者备忘录

# 本地环境构建和调试
  1. 安装标准环境google cloud SDK/gloud CLI，并且执行 gcloud init
  2. 安装依赖 `pip install requirements.txt`
  3. 使用命令打开调试环境
     `c:\python38\python.exe "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\dev_appserver.py" --runtime_python_path="python27=c:\python27\python.exe,python3=c:\python38\python.exe"  --skip_sdk_update_check=true app.yaml worker.yaml`
     `--support_datastore_emulator=true`

  2. 即使在本机，GAE应用也运行在一个沙箱内，无法读写本机文件，如果要突破，可以修改 stubs.py 里面的 FakeFile 类。
     * 删除__init__()
     * is_file_accessible() 无条件返回 FakeFile.Visibility.OK
     * stubs.py默认位置：C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\platform\google_appengine\google\appengine\tools\devappserver2\python\runtime\stubs.py

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

# Windows 安装配置 MongoDB
* 下载安装后创建一个目录保存数据库文件，比如 c:\mongodb\db
* 安装启动服务
  >`"C:\Program Files\MongoDB\Server\3.6\bin\mongod.exe" --dbpath "c:\mongodb\db" --logpath "c:\mongodb\log\MongoDB.log" --install --serviceName "MongoDB"  --journal`
  > `net start MongoDB`
  > `"C:\Program Files\MongoDB\Server\3.6\bin\mongo.exe"`
  > `db.Book.insert({"name":"1001 nights"})`
  > `db.Book.find()`
* 其他命令
  > `net stop MongoDB`  #停止后台服务
  > `mongod.exe --remove`  #删除后台服务`

# KindleEar额外自带的Python库，这些库不用pip安装，不在requirements.txt里面
* readability-lxml: 修改了其htmls.py|shorten_title()

# 常用链接
[App Engine 文档](https://cloud.google.com/appengine/docs)
[Cloud Tasks]https://cloud.google.com/tasks/docs