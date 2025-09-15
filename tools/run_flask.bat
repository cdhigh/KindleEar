mode con: cols=160 lines=1000
E:
cd E:\Programer\Project\KindleEar
set FLASK_APP=main.py
set APP_DOMAIN=http://localhost:5000/
set DATABASE_URL=sqlite:///database.db
::set DATABASE_URL=pickle:///database.pkl
set TASK_QUEUE_SERVICE=apscheduler
set TASK_QUEUE_BROKER_URL=memory
set KE_TEMP_DIR=E:/temp
set EBOOK_SAVE_DIR=E:/webshelf
set DICTIONARY_DIR=E:/webshelf
set LOG_LEVEL=info
set HIDE_MAIL_TO_LOCAL=no
python -m flask run --host=0.0.0.0 --debug
pause
