# Large multipart uploads can take longer than Gunicorn's 30-second default.
timeout = 180
graceful_timeout = 30
