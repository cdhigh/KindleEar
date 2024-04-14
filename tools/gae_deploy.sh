#!/bin/bash
gcloud config set project $GOOGLE_CLOUD_PROJECT
gcloud app create   #select a region for app if it's first time
python ./kindleear/tools/update_req.py gae
if [ $? -eq 0 ]; then
  gcloud beta app deploy --version=1 ./kindleear/app.yaml
  gcloud beta app deploy --version=1 ./kindleear/cron.yaml
  gcloud beta app deploy --version=1 ./kindleear/queue.yaml
  echo -e "The deployment is completed."
  echo -e "The access address is: https://$GOOGLE_CLOUD_PROJECT.appspot.com"
else
  echo -e "The deployment is terminated."
  exit 1
fi

