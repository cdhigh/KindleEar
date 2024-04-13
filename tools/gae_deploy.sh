#!/bin/bash
gcloud app create   #select a region for app if it's first time
python ./tools/update_req.py gae
gcloud beta app deploy --version=1 app.yaml
gcloud beta app deploy --version=1 cron.yaml
gcloud beta app deploy --version=1 queue.yaml
echo -e "The deployment is completed."
echo -e "The access address is: https://$GOOGLE_CLOUD_PROJECT.appspot.com"
