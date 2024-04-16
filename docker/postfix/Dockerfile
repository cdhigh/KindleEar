# Inspired by <https://github.com/thingless/mailglove>
From alpine:3.19.1

ADD install.sh /etc/postfix/install.sh

RUN apk add --no-cache curl bash postfix && \
    newaliases && \
    chmod 755 /etc/postfix/install.sh

EXPOSE 25

CMD ["/etc/postfix/install.sh"]
