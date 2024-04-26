#!/bin/bash
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
  read -p "Please input your project ID: " GOOGLE_CLOUD_PROJECT
  if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
    echo "Error: Project ID cannot be empty."
    exit 1
  fi
  export GOOGLE_CLOUD_PROJECT
fi
gcloud config set project $GOOGLE_CLOUD_PROJECT
if ! gcloud app describe >/dev/null 2>&1; then
  gcloud app create   #select a region for app if it's first time
fi

if python ./kindleear/tools/update_req.py gae; then
  gcloud services enable firestore.googleapis.com datastore.googleapis.com \
  cloudtasks.googleapis.com cloudscheduler.googleapis.com appenginereporting.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com cloudtrace.googleapis.com \
  containerregistry.googleapis.com firebaserules.googleapis.com logging.googleapis.com \
  pubsub.googleapis.com storage-api.googleapis.com
  
  gcloud beta app deploy --version=1 ./kindleear/app.yaml
  gcloud beta app deploy --quiet --version=1 ./kindleear/worker.yaml
  gcloud beta app deploy --quiet --version=1 ./kindleear/cron.yaml
  gcloud beta app deploy --quiet --version=1 ./kindleear/queue.yaml
  gcloud beta app deploy --quiet --version=1 ./kindleear/dispatch.yaml
  echo -e "The deployment is completed."
  echo -e "The access address is: https://$GOOGLE_CLOUD_PROJECT.appspot.com"
else
  echo -e "Error: Update requirements failed. The deployment is terminated."
  exit 1
fi
