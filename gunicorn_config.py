# gunicorn_config.py
bind = "0.0.0.0:10000"
workers = 1
threads = 2
timeout = 300  # Increased from 120 to 300 seconds
graceful_timeout = 60
max_requests = 500
max_requests_jitter = 50
loglevel = "info"
worker_class = "sync"
keepalive = 10