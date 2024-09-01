from app.models import ChatRooms, GameRecords
import random
import string
import time
from .jwt import validate_access_token
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

def genResponse(status: bool, message: str, data: dict | None) -> dict:
    if status:
        return {
            "status": True,
            "message": message,
            "data": data
        }
    else:
        return {
            "status": False,
            "message": message,
            "data": None
        }
        
def generateRandomID(lookup, length=6) -> str:
    id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    match lookup:
        case 'chatroom':
            while ChatRooms.objects.filter(chat_id=id).exists():
                id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        case 'gamerecords':
            while GameRecords.objects.filter(game_id=id).exists():
                id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        case _:
            raise ValueError('Invalid lookup')
    return id

def gameTread(self, game):
    while True:
        game.update()
        print("thread")
        time.sleep(1)
        if game.end_game() or game.timeout():
            break

def cookieParser(cookie):
    cookies = {}
    for c in cookie.decode().split('; '):
        key, value = c.split('=')
        cookies[key] = value
    return cookies

def findCookie(scope):
    for header in scope['headers']:
        if header[0] == b'cookie':
            return cookieParser(header[1])

def checkAuthForWS(scope) -> None | dict:
    cookies = findCookie(scope)
    if not cookies:
        return None
    user_payload = cookies['access_token']
    if not user_payload:
        return None
    user_data = validate_access_token(user_payload)
    return user_data

def threaded(fn):
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
        return thread
    return wrapper

def synchronized_method(method):
    outer_lock = threading.Lock()
    lock_name = "__"+method.__name__+"_lock"+"__"
    
    def sync_method(self, *args, **kws):
        with outer_lock:
            if not hasattr(self, lock_name): setattr(self, lock_name, threading.Lock())
            lock = getattr(self, lock_name)
            with lock:
                return method(self, *args, **kws)  

    return sync_method