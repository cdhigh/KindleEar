#!/bin/sh

if [ "$RANDOMIZE_SECRET_KEY" != "no" ]; then
  if command -v hexdump > /dev/null 2>&1; then
    export SECRET_KEY=$(hexdump -n 12 -v -e '/1 "%02x"' /dev/urandom)
  elif command -v od > /dev/null 2>&1; then
    export SECRET_KEY=$(od -N 12 -A n -t x1 /dev/urandom | tr -d ' \n')
  elif command -v xxd > /dev/null 2>&1; then
    export SECRET_KEY=$(xxd -l 12 -p /dev/urandom)
  else
    echo "No command found for SECRET_KEY, using default."
  fi
fi

if [ -z "$TZ" ]; then
  export TZ=Etc/GMT+0
fi

exec /usr/local/bin/gunicorn -c /usr/kindleear/gunicorn.conf.py main:app
