print "celeryconfig now"
CELERY_TASK_SERIALIZER = 'json'
BROKER_TRANSPORT = "mongodb"
BROKER_URL = "mongodb://bang:27017/photoQueue"
BROKER_HOST = "bang"
BROKER_TRANSPORT_OPTIONS = {
    "host": "bang",
    "database": "photoQueue",
    }
CELERY_MONGODB_BACKEND_SETTINGS = BROKER_TRANSPORT_OPTIONS
CELERY_TRACK_STARTED = True
CELERY_RESULT_BACKEND = BROKER_URL
