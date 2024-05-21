#!/bin/bash
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
  echo ""
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

SH_DIR="$(dirname "$0")"
KE_DIR="$(dirname "$SH_DIR")"

if python ${SH_DIR}/update_req.py gae[$@]; then
  echo "Enabling APIs..."
  gcloud services enable firestore.googleapis.com datastore.googleapis.com \
  cloudtasks.googleapis.com cloudscheduler.googleapis.com appenginereporting.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com cloudtrace.googleapis.com \
  containerregistry.googleapis.com firebaserules.googleapis.com logging.googleapis.com \
  pubsub.googleapis.com storage-api.googleapis.com

  gcloud beta app deploy --version=1 ${KE_DIR}/app.yaml ${KE_DIR}/worker.yaml
  gcloud beta app deploy --quiet --version=1 ${KE_DIR}/cron.yaml
  gcloud beta app deploy --quiet --version=1 ${KE_DIR}/queue.yaml
  gcloud beta app deploy --quiet --version=1 ${KE_DIR}/dispatch.yaml
  echo -e "The deployment is completed."
  echo -e "The access address is: https://$GOOGLE_CLOUD_PROJECT.appspot.com"
else
  echo -e "Error: Update requirements failed. The deployment is terminated."
  exit 1
fi
