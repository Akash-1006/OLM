# -------------------------
# SERVER
# -------------------------
bind             = "127.0.0.1:5003"
backlog          = 1024
worker_class     = "sync"
workers          = 1
timeout          = 60
keepalive        = 5
preload_app      = False
graceful_timeout = 30
accesslog        = "logs/access.log"
errorlog         = "logs/error.log"
loglevel         = "info"
capture_output   = True
access_log_format = '%(h)s - - [%(t)s] "%(m)s %(U)s %(H)s" %(s)s -'
daemon           = False
pidfile          = "logs/gunicorn.pid"
proc_name        = "Titans_webhook"
