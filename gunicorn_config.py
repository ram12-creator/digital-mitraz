# gunicorn_config.py
import multiprocessing

# Bind to port
bind = "0.0.0.0:10000"

# Use only 1 worker on free tier (critical for memory)
workers = 1

# Use threads instead of multiple processes (less memory)
threads = 2

# Timeout settings
timeout = 120
graceful_timeout = 30

# Memory limits
max_requests = 100
max_requests_jitter = 10

# Log level
loglevel = "info"

# Worker class - sync is fine for single worker
worker_class = "sync"

# Disable keep-alive to free memory
keepalive = 5