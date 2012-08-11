# ../bin/celery -A worker worker --loglevel=info

from celery import Celery
from celery import current_task
import sys, traceback

sys.path.append("..")
import photos

celery = Celery('worker')
class Config(object):
    CELERY_TASK_SERIALIZER = 'json'
    BROKER_TRANSPORT = "mongodb"
    BROKER_URL = "mongodb://bang:27017/photoQueue"
    BROKER_TRANSPORT_OPTIONS = {
        "host": "bang",
        "database": "photoQueue",
        }
    CELERY_RESULT_BACKEND = "mongodb"
    CELERY_MONGODB_BACKEND_SETTINGS = BROKER_TRANSPORT_OPTIONS
celery.config_from_object(Config)


@celery.task
def justCache(uri, sizes):
    #current_task.update_state(state='PROGRESS', meta={'current': 'x'})
    photos.justCache(uri, sizes)

if __name__ == '__main__':
    celery.worker_main()
