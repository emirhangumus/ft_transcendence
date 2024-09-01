import json
from .models import Notifications
import asyncio
from .utils import threaded, synchronized_method

class NotificationManager:
    types = ['normal', 'friend_request', 'match_invite', 'match_result']
    started = False
    
    def __init__(self):
        self.notifications = {}
        self.queue = {}
        
    def register_user(self, ws, user_id):
        self.notifications[user_id] = {
            'ws': ws,
        }
        self.queue[user_id] = []
        
    def unregister_user(self, user_id):
        if user_id in self.notifications:
            del self.notifications[user_id]
        if user_id in self.queue:
            del self.queue[user_id]

    def add_notification(self, user_id, message, payload={}, type='normal'):
        if user_id in self.queue:
            self.queue[user_id].append({
                'message': message,
                'payload': payload,
                'type': type
            })
        else:
            self.queue[user_id] = [{
                'message': message,
                'payload': payload,
                'type': type
            }]
    
    def start(self):
        if self.started:
            return
        if not self.started:
            self.started = True
        self.__start()
    
    @threaded
    def __start(self):
        while True:
            asyncio.run(self.process_queue())
    
    async def process_queue(self):
        for user_id in self.queue:
            for notification in self.queue[user_id]:
                await self.__send_notification(user_id, notification['message'], notification['payload'], notification['type'])
        self.queue = {}
        await asyncio.sleep(0.5)

    async def get_notifications(self, user_id, is_read='all'):
        if is_read == 'all':
            notifications = Notifications.objects.filter(receiver=user_id)
        else:
            if is_read == 'yes':
                is_read = True
            else:
                is_read = False
            notifications = Notifications.objects.filter(receiver=user_id, is_read=is_read)
        return notifications
    
    async def mark_as_read_all(self, user_id):
        notifications = Notifications.objects.filter(receiver=user_id, is_read=False)
        for notification in notifications:
            notification.is_read = True
            notification.save()
    
    async def __send_notification(self, user_id, message, payload={}, type='normal'):
        # user = User.objects.get(id=user_id)
        index = self.types.index(type)
        type = self.types[index]
        # Notifications.objects.create(receiver=user, message=notification, payload=payload, type=type)
        if user_id in self.notifications:
            await self.notifications[user_id]['ws'].send(text_data=json.dumps({
                'type': 'notifications',
                'notification': {
                    'message': message,
                    'payload': payload,
                    'type': type
                }
            }))
        else:
            print('User not found for notification')

    @synchronized_method
    def _get_notification_(self):
        return self.notifications