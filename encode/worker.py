# ../bin/celery -A worker worker --loglevel=info

from celery import Celery
from celery import current_task
import sys

sys.path.append("..")
import photos

celery = Celery('worker')
celery.conf.update(dict(
        CELERY_RESULT_BACKEND = "mongodb",
        CELERY_MONGODB_BACKEND_SETTINGS = {
            "host": "bang",
            "database": "photoQueue",
            }
        ))

@celery.task
def justCache(uri, sizes):
    #current_task.update_state(state='PROGRESS', meta={'current': 'x'})
    photos.justCache(uri, sizes)


if __name__ == '__main__':
    celery.worker_main()
