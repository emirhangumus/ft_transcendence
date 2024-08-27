import os
from concurrent.futures import ThreadPoolExecutor

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from asgiref.sync import SyncToAsync

from . import routing

SyncToAsync.single_thread_executor = ThreadPoolExecutor(max_workers=5)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')


django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    'websocket': URLRouter(routing.websocket_urlpattern,),
    "http": django_asgi_app,
})