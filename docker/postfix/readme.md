# Mailfix

This is a Postfix image inspired by <https://github.com/thingless/mailglove>, providing the same functionality (almost). The purpose is to intercept all emails received by Postfix and then call a webhook URL passed through environment variables.    


# Why create Mailfix when Mailglove already exists?    
Mailglove is too large, with a size of 124MB before decompression and 338MB after decompression. It's not worth consuming so much space for such a simple function.    
Therefore, I replaced Ubuntu with Alpine and Node.js with shell scripts, moved the email parsing functionality to the client side.    
Apart from the Alpine image and Postfix, there is actually only one shell script. After decompression, the image size is only 26.8MB.    


# mailfix
这个是postfix的镜像，灵感来自 <https://github.com/thingless/mailglove> ，功能差不多一样。
功能是拦截postfix接收到的所有邮件，然后调用通过环境变量传入的webhook url。


# 为什么有了mailglove还需要制作mailfix？
mailglove太大了，解压前124MB，解压后338M，为了这么一个简单的功能消耗那么大的空间实在不值得。   
所以我就使用alpine代替ubuntu，使用sh代替nodejs，邮件解析功能移到客户端。    
除了alpine镜像和postfix，实际上只有一个sh文件，镜像解压后只有26.8M。    

