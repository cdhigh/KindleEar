D:
cd D:\Programer\Project\KindleEar
set FLASK_APP=main.py
set APP_DOMAIN=http://localhost:5000/
set DATABASE_URL=sqlite:///database.db
set TASK_QUEUE_SERVICE=apscheduler
set TASK_QUEUE_BROKER_URL=redis://127.0.0.1:6379/
set KE_TEMP_DIR=d:/temp
set LOG_LEVEL=debug
python -m flask run --host=0.0.0.0 --debug
pause
