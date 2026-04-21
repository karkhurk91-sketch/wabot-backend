from celery import Celery
from modules.common.config import REDIS_URL

celery_app = Celery("wabot", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
)

def enqueue_message(message_dict: dict):
    celery_app.send_task("process_incoming_message", args=[message_dict])
