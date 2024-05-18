#!/bin/bash

CONTAINER_NAME="kindleear_container"
IMAGE_NAME="kindleear/kindleear:latest"
SSL_CERT="fullchain.pem"
SSL_KEY="privkey.pem"

# Set default domain
DOMAIN=${1:-"example.com"}

# Create data directory if it doesn't exist
if [ ! -d "./data" ]; then
    echo "Creating ./data directory..."
    mkdir ./data
fi

# Check if SSL certificate files exist
if [ -f "./data/$SSL_CERT" ] && [ -f "./data/$SSL_KEY" ]; then
    echo "Found SSL certification, enable both HTTP and HTTPS."
    SSL_ENV="-e GUNI_CERT=/data/$SSL_CERT -e GUNI_KEY=/data/$SSL_KEY"
    SSL_PORT="-p 443:8000"
else
    echo "Found no SSL certification, Only HTTP enabled."
    SSL_ENV=""
    SSL_PORT=""
fi

echo "Stopping and removing existing KindleEar..."
sudo docker stop $CONTAINER_NAME
sudo docker rm $CONTAINER_NAME

echo "Pulling the latest version of the KindleEar..."
sudo docker pull $IMAGE_NAME

echo "Starting the updated KindleEar with domain: [$DOMAIN] ..."
sudo docker run -d -p 80:8000 $SSL_PORT -v $(pwd)/data:/data --restart always -e TZ=Etc/GMT+0 -e APP_DOMAIN=$DOMAIN $SSL_ENV --name $CONTAINER_NAME $IMAGE_NAME

echo ""
echo -e "\033[1;32mKindleEar updated successfully.\033[0m"
echo ""
