timeout_keep_alive = 300
timeout_graceful_shutdown = 300
timeout_notify = 300
timeout_worker = 300

# Increase the default timeout for workers
workers_per_core = 1
worker_class = "uvicorn.workers.UvicornWorker" 