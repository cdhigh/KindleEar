#!/bin/bash

#steal from https://github.com/thingless/mailglove
postconf -e myhostname=${DOMAIN}

# Add the myhook hook to the end of master.cf
if ! grep -qF 'myhook unix - n n - - pipe' /etc/postfix/master.cf; then
tee -a /etc/postfix/master.cf <<EOF
myhook unix - n n - - pipe
    flags=F user=nobody argv=curl -X POST --data-binary @- ${URL}
EOF
fi

# Enable logging output to stdout with postlog daemon
if ! grep -qF 'postlog   unix-dgram n  -       n       -       1       postlogd' /etc/postfix/master.cf; then
tee -a /etc/postfix/master.cf <<'EOF'
postlog   unix-dgram n  -       n       -       1       postlogd
EOF
fi

# Make SMTP use myhook
postconf -F 'smtp/inet/command = smtpd -o content_filter=myhook:dummy'

# Disable bounces
postconf -F 'bounce/unix/command = discard'

# Disable local recipient maps so nothing is dropped b/c of non-existent email
postconf -e 'local_recipient_maps ='

#postconf -e 'mydestination = localhost'

# Enable logging to foreground in postlog
postconf -e 'maillog_file = /dev/stdout'

# Set the max size ~= 30MB
postconf -e message_size_limit=35000000

#############
## Enable TLS
#############
#if [[ -n "$(find /etc/postfix/certs -iname *.crt)" && -n "$(find /etc/postfix/certs -iname *.key)" ]]; then
#  # /etc/postfix/main.cf
#  postconf -e smtpd_tls_cert_file=$(find /etc/postfix/certs -iname *.crt)
#  postconf -e smtpd_tls_key_file=$(find /etc/postfix/certs -iname *.key)
#  chmod 400 /etc/postfix/certs/*.*
#  # /etc/postfix/master.cf
#  postconf -M submission/inet="submission   inet   n   -   n   -   -   smtpd"
#  postconf -P "submission/inet/syslog_name=postfix/submission"
#  postconf -P "submission/inet/smtpd_tls_security_level=encrypt"
#  postconf -P "submission/inet/smtpd_sasl_auth_enable=yes"
#  postconf -P "submission/inet/milter_macro_daemon_name=ORIGINATING"
#  postconf -P "submission/inet/smtpd_recipient_restrictions=permit_sasl_authenticated,reject_unauth_destination"
#fi

echo "[ Starting Postfix... ]"
/usr/sbin/postfix start-fg
