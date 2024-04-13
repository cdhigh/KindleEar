#!/bin/bash
gcloud app create   #select a region for app if it's first time
python ./kindleear/tools/update_req.py gae
gcloud beta app deploy --version=1 ./kindleear/app.yaml
gcloud beta app deploy --version=1 ./kindleear/cron.yaml
gcloud beta app deploy --version=1 ./kindleear/queue.yaml
echo -e "The deployment is completed."
echo -e "The access address is: https://$GOOGLE_CLOUD_PROJECT.appspot.com"
