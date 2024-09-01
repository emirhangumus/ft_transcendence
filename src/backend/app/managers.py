import json
from .models import Notifications, Tournaments
import asyncio
from .utils import threaded, synchronized_method
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User

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
        
    @sync_to_async
    def get_notifications(self, user_id, is_read='all'):
        if is_read == 'all':
            notifications = Notifications.objects.filter(receiver=user_id)
        else:
            if is_read == 'yes':
                is_read = True
            else:
                is_read = False
            notifications = Notifications.objects.filter(receiver=user_id, is_read=is_read)
        return notifications
        
    def unregister_user(self, user_id):
        if user_id in self.notifications:
            del self.notifications[user_id]
        if user_id in self.queue:
            del self.queue[user_id]

    def add_notification(self, user_id, message, payload={}, type='normal', add_to_db=False):
        if user_id in self.queue:
            self.queue[user_id].append({
                'message': message,
                'payload': payload,
                'type': type,
                'add_to_db': add_to_db
            })
        else:
            self.queue[user_id] = [{
                'message': message,
                'payload': payload,
                'type': type,
                'add_to_db': add_to_db
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
            asyncio.run(self.__process_queue())
    
    async def __process_queue(self):
        for user_id in self.queue:
            for notification in self.queue[user_id]:
                await self.__send_notification(user_id, notification['message'], notification['payload'], notification['type'], notification['add_to_db'])
        self.queue = {}
        await asyncio.sleep(0.5)

    async def mark_as_read_all(self, user_id):
        await self.mark_as_read_all_sync(user_id)
    
    async def __send_notification(self, user_id, message, payload={}, type='normal', add_to_db=True):
        if add_to_db:
            user = await self.get_user(user_id)
            notification = await self.create_notification(user, message, payload, type)
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
    
    @sync_to_async
    def get_user(self, user_id):
        return User.objects.get(id=user_id)
    
    @sync_to_async
    def create_notification(self, user, message, payload={}, type='normal'):
        index = self.types.index(type)
        type = self.types[index]
        payload = { "message": message, **payload }
        return Notifications.objects.create(receiver=user, payload=payload, type=type)

    @sync_to_async
    def mark_as_read_all_sync(self, user_id):
        user = User.objects.get(id=user_id)
        notifications = Notifications.objects.filter(receiver=user, is_read=False)
        for notification in notifications:
            notification.is_read = True
            notification.save()
            
class Tournament:
    started = False
    game_started = False
    
    def __init__(self, players, manager):
        self.players = players
        self.manager = manager
        
    def start(self):
        if self.started:
            return
        if not self.started:
            self.started = True
        self.__start()
        
    @threaded
    def __start(self):
        while True:
            asyncio.run(self.__process())
    
    async def __process(self):
        pass
    
    def add_player(self, player, channel):
        if player.id in self.players or self.game_started:
            return
        self.players[player.id] = {
            'channel': channel,
            'player': player
        }
    
    def remove_player(self, player):
        if player.id in self.players:
            del self.players[player.id]
    
    def end(self):
        pass
    
    def get_players(self):
        return self.players
    
class TournamentManager:
    tournaments = {}
    started = False
    
    def __init__(self):
        self.tournaments = {}

    def add_tournament(self, tournament_id):
        self.tournaments[tournament_id] = Tournament({}, self)
        # self.tournaments[tournament_id].start()
        
    def add_player(self, tournament_id, player, channel):
        if tournament_id not in self.tournaments:
            return
        if player.id in self.tournaments[tournament_id].get_players():
            return
        self.tournaments[tournament_id].add_player(player, channel)
        
    def remove_player(self, tournament_id, player):
        if tournament_id not in self.tournaments:
            return
        self.tournaments[tournament_id].remove_player(player)
    
    def start(self):
        if self.started:
            return
        if not self.started:
            self.started = True
        self.__start()
    
    @threaded
    def __start(self):
        asyncio.run(self.initial_up())
        while True:
            asyncio.run(self.__process())
        
    async def __process(self):
        # for tournament_id in self.tournaments:
            # await self.tournaments[tournament_id].__process()
        await asyncio.sleep(0.2)
    
    async def initial_up(self):
        tournaments = list(await self.get_pending_tournaments())
        for tournament in tournaments:
            self.tournaments[tournament.tournament_id] = Tournament({}, self)
            self.tournaments[tournament.tournament_id].start()
        print(self.tournaments)

    @sync_to_async
    def get_pending_tournaments(self):
        t = Tournaments.objects.filter(status='pending')
        return [i for i in t]
