# gunicorn.conf.py
pythonpath = "/home/ubuntu/.local/lib/python3.10/site-packages"
bind = "127.0.0.1:8000"
workers = 1
threads = 3
#accesslog = "/var/log/gunicorn/error.log"
#errorlog = "/var/log/gunicorn/access.log"
capture_output = True
enable_stdio_inheritance = True
#loglevel = "info"
#preload_app = True
#certfile = 'cert.pem'
#keyfile = 'key.pem'
#example: https://github.com/benoitc/gunicorn/blob/master/gunicorn/glogging.py
logconfig_dict = {
    'version': 1,
    'disable_existing_loggers': False,
    "root": {"level": "INFO", "handlers": ["error_file", "access_file"]},
    'loggers': {
        "gunicorn.error": {
            "level": "INFO", 
            "handlers": ["error_file"],
            "propagate": 1,
            "qualname": "gunicorn.error"
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["access_file"],
            "propagate": 0,
            "qualname": "gunicorn.access"
        }
    },
    'handlers': {
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "maxBytes": 50*1024*1024, #50M
            "backupCount": 1,
            "formatter": "generic",
            #'mode': 'w+',
            "filename": "/data/gunicorn.error.log"
        },
        "access_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "maxBytes": 10*1024*1024, #10M
            "backupCount": 1,
            "formatter": "generic",
            "filename": "/data/gunicorn.access.log"
        }
    },
    'formatters':{
        "generic": {
            "format": "'[%(process)d] [%(asctime)s] %(levelname)s [%(filename)s:%(lineno)s] %(message)s'",
            "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
            "class": "logging.Formatter"
        },
        "access": {
            "format": "'[%(process)d] [%(asctime)s] %(levelname)s [%(filename)s:%(lineno)s] %(message)s'",
            "class": "logging.Formatter"
        }
    }
}
