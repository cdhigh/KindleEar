# gunicorn.conf.py
pythonpath = "/usr/local/lib/python3.10/site-packages"
bind = "0.0.0.0:8000"
workers = 1
threads = 3
accesslog = "/data/gunicorn.access.log"
errorlog = "/data/gunicorn.error.log"
capture_output = True
enable_stdio_inheritance = True
loglevel = "info"
#preload_app = True
#certfile = 'cert.pem'
#keyfile = 'key.pem'
