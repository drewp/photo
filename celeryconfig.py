BROKER_URL = 'mongodb://bang:27017/photoQueue'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TRACK_STARTED = True
CELERY_TASK_SERIALIZER = 'json'
CELERY_IMPORTS = ['worker']
