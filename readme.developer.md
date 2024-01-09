# KindleEar面向开发者备忘录

# 本地环境构建和调试
  1. 安装GAE SDK后，使用命令打开调试环境
     `dev_appserver.py app.yaml module-worker.yaml`
  c:\python38\python.exe "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\dev_appserver.py" --runtime_python_path="python27=c:\python27\python.exe,python3=c:\python38\python.exe" --support_datastore_emulator=true --skip_sdk_update_check=true app.yaml worker.yaml

  2. 即使在本机，GAE应用也运行在一个沙箱内，无法读写本机文件，如果要突破，可以修改 stubs.py 里面的 FakeFile 类。
     * 删除__init__()
     * is_file_accessible() 无条件返回 FakeFile.Visibility.OK
     * stubs.py默认位置：C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\platform\google_appengine\google\appengine\tools\devappserver2\python\runtime\stubs.py

# KindleEar额外自带的Python库，这些库不用pip安装，不在requirements.txt里面
* readability-lxml: 修改了其htmls.py|shorten_title()


# 常用链接
[App Engine 文档](https://cloud.google.com/appengine/docs)
[Cloud Tasks]https://cloud.google.com/tasks/docs