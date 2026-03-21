from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/engine/jobs/(?P<job_id>[0-9a-fA-F-]+)/progress/$', consumers.JobProgressConsumer.as_asgi()),
]
