# gunicorn.conf.py
pythonpath = "/home/ubuntu/.local/lib/python3.10/site-packages"
bind = "127.0.0.1:8000"
workers = 2
accesslog = "/home/ubuntu/log/gunicorn.access.log"
errorlog = "/home/ubuntu/log/gunicorn.error.log"
capture_output = True
loglevel = "info"
preload_app = True
#certfile = 'cert.pem'
#keyfile = 'key.pem'
