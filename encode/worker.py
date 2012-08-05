# ../bin/celery -A worker worker --loglevel=info

from celery import Celery
from celery import current_task
import sys

sys.path.append("..")
import photos

celery = Celery('worker',
                broker='mongodb://bang:27017/photoQueue',
                backend='mongodb',
                serializer='json')

@celery.task
def justCache(uri, sizes):
    #current_task.update_state(state='PROGRESS', meta={'current': 'x'})
    photos.justCache(uri, sizes)

