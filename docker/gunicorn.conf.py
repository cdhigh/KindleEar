# gunicorn.conf.py
import os
pythonpath = "/usr/local/lib/python3.9/site-packages"
bind = "0.0.0.0:8000"
workers = 1
threads = 3
capture_output = True
enable_stdio_inheritance = True
#accesslog = "/data/gunicorn.access.log"
#errorlog = "/data/gunicorn.error.log"
#loglevel = "info"
#preload_app = True
certfile = os.getenv('GUNI_CERT')
keyfile = os.getenv('GUNI_KEY')
#example: https://github.com/benoitc/gunicorn/blob/master/gunicorn/glogging.py
logconfig_dict = {
    'version': 1,
    'disable_existing_loggers': False,
    "root": {"level": "INFO", "handlers": ["error_file"]},
    'loggers': {
        "gunicorn.error": {
            "level": "INFO", 
            "handlers": ["error_file"],
            "propagate": False,
            "qualname": "gunicorn.error"
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["access_file"],
            "propagate": False,
            "qualname": "gunicorn.access"
        }
    },
    'handlers': {
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "maxBytes": 2*1024*1024, #2M, >20000lines
            "backupCount": 1,
            "formatter": "generic",
            "filename": "/data/gunicorn.error.log"
        },
        "access_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "maxBytes": 500*1024, #500K >3000lines
            "backupCount": 1,
            "formatter": "access",
            "filename": "/data/gunicorn.access.log"
        }
    },
    'formatters':{
        "generic": {
            "format": "%[(asctime)s] %(levelname)s [%(filename)s:%(lineno)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S %z",
            "class": "logging.Formatter"
        },
        "access": {
            "format": "%(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S %z",
            "class": "logging.Formatter"
        }
    }
}
