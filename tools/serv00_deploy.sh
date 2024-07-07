#!/bin/bash
echo ""
read -p "Please input your serv00 id: " SERV00_USER
if [ -z "$SERV00_USER" ]; then
  echo "Error: Project ID cannot be empty."
  exit 1
fi

DOMAIN="${SERV00_USER}.serv00.net"
VENV_DIR="/usr/home/${SERV00_USER}/.virtualenvs"
SITE_DIR="/usr/home/${SERV00_USER}/domains/${DOMAIN}/public_python"
export SERV00_USER
export VENV_DIR
export SITE_DIR

echo "Creating virtual env..."
mkdir $VENV_DIR
cd $VENV_DIR
virtualenv ke
source ${VENV_DIR}/ke/bin/activate

#split into small batches to avoid serv00 memory limit
pip install lxml~=5.2.0 #failed
pip install requests~=2.32.0 chardet~=5.2.0 pillow~=10.3.0 lxml_html_clean~=0.1.1
pip install sendgrid~=6.11.0 mailjet_rest~=1.3.4 python-dateutil~=2.9.0 css_parser~=1.0.10
pip install beautifulsoup4~=4.12.2 html2text~=2024.2.26 html5lib~=1.1 Flask~=3.0.3 flask-babel~=4.0.0
pip install six~=1.16.0 feedparser~=6.0.11 qrcode~=7.4.2 gtts~=2.5.1 edge-tts~=6.1.11 justext~=3.0.1
pip install peewee~=3.17.1 flask-apscheduler~=1.13.1 marisa_trie~=1.2.0 indexed-gzip~=1.8.7
wget https://github.com/cdhigh/chunspell/releases/download/2.0.4/chunspell-2.0.4-freebsd-amd64.zip
unzip -y -d ./chunspell_whl/ chunspell-2.0.4-freebsd-amd64.zip
pip install chunspell --no-index --find-links=./chunspell_whl/.
rm -rf ./chunspell_whl

devil www add $DOMAIN python ${VENV_DIR}/ke/bin/python production
cd ${SITE_DIR}
echo "import sys, os\nsys.path.append(os.getcwd())\nfrom kindleear import app as application" > ${SITE_DIR}/passenger_wsgi.py
rm -f ${SITE_DIR}/public/index.html
rm -rf ${SITE_DIR}/kindleear
git clone --depth 1 https://github.com/cdhigh/kindleear.git

#TODO: change config.py
#TODO: add cron

devil www restart $DOMAIN
