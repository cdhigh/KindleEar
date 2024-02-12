D:
cd D:\Programer\Project\KindleEar
celery -A main.celery_app worker --loglevel=info --concurrency=2 -P eventlet
