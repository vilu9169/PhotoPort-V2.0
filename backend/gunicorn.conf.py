# Large multipart uploads can take longer than Gunicorn's 30-second default.
timeout = 180
graceful_timeout = 30

# Keep image processing within Render's 512 MB instance limit. Derivative work
# runs in a background thread, so additional worker processes only duplicate
# the application's memory footprint.
workers = 1
