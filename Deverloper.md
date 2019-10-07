# KindleEar面向开发者备忘录

# 本地环境构建和调试
  1. 安装GAE SDK后，使用命令打开调试环境
     `dev_appserver.py app.yaml module-worker.yaml`

  2. 即使在本机，GAE应用也运行在一个沙箱内，无法读写本机文件，如果要突破，可以修改 stubs.py 里面的 FakeFile 类。
     * 删除__init__()
     * is_file_accessible() 无条件返回 FakeFile.Visibility.OK
     * stubs.py默认位置：C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\platform\google_appengine\google\appengine\tools\devappserver2\python\runtime\stubs.py
