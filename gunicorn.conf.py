"""Gunicorn configuration for multi-worker production deployment."""

import multiprocessing
import os

# Bind
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# Workers: CPU cores * 2 + 1 is a common heuristic, capped for sanity
workers = int(os.getenv("WORKERS", min(multiprocessing.cpu_count() * 2 + 1, 8)))
worker_class = "uvicorn.workers.UvicornWorker"

# Timeouts
timeout = 60
graceful_timeout = 30
keepalive = 5

# Limits
max_requests = 2000
max_requests_jitter = 200

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
