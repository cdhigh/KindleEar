# mailfix介绍
这个是postfix的镜像，灵感来自 <https://github.com/thingless/mailglove> ，功能完全一样。
功能是拦截postfix接收到的所有邮件，然后调用通过环境变量传入的URL的webhook。

# 为什么有了mailglove还需要制作mailfix？
mailglove太大了，解压前124MB，解压后338M，为了这么一个简单的功能消耗那么大的空间实在不值得。
所以我就使用alpine代替ubuntu，使用sh代替nodejs。
除了alpine镜像和postfix，实际上只有一个sh文件，镜像解压后只有26.8M。

