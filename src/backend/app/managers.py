import json
from .models import Notifications, Tournaments
import asyncio
from .utils import threaded, synchronized_method
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
import random

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
    notify_players_for_user_change = False
    tournament_owner = None
    tournament_id = None
    tournament_deleted = False
    
    fixtures = []
    
    def __init__(self, players, manager):
        self.players = players
        self.manager = manager
        
    def start(self, tournament_id=None):
        if self.started:
            return
        if not self.started:
            self.started = True
        self.tournament_id = tournament_id
        self.__start()
        
    @threaded
    def __start(self):
        asyncio.run(self.__init_tournament())
        while True:
            if self.tournament_deleted:
                break
            asyncio.run(self.__process())
            if self.tournament_deleted:
                break
        if self.tournament_deleted:
            asyncio.run(self.remove_tournament(self.tournament_id))
            
    async def __init_tournament(self):
        pass
        
    async def __process(self):
        if self.game_started:
            if (len(self.fixtures) == 0):
                # prepare the fixtures
                await self.__prepare_fixtures()
        else:
            await self.__tournament_ownership()
            if self.tournament_deleted:
                return
            await self.__send_player()
            if self.tournament_deleted:
                return
        await asyncio.sleep(0.2)
    
    async def __prepare_fixtures(self):
        # prepare the fixtures. If the number of players is odd
        self.fixtures = []
        
        random_players = list(self.players.keys())
        random.shuffle(random_players)
        
        section_number = len(random_players) // 2
        
        
        pass
    
    async def __tournament_ownership(self):
        if self.tournament_owner is None:
            tournament = await self.get_tournament(self.tournament_id)
            
            # print all the data in the tournament
            if tournament is None:
                self.tournament_deleted = True
                return

            self.tournament_id = tournament.tournament_id
            self.tournament_owner = await self.get_user(tournament.created_by_id)
        # if the owner is not in the players, remove the tournament
    
    async def __send_player(self):
        if self.notify_players_for_user_change:
            # if the leaved player is the owner, change the ownership
            if self.tournament_owner.id not in self.players:
                if len(self.players) > 0:
                    # 0 is the first player
                    player_id = list(self.players.keys())[0]
                    await self.change_tournament_ownership(self.tournament_id, player_id)
                    self.tournament_owner = await self.get_user(player_id)
                    self.notify_players_for_user_change = True
                        
            # send the new player to all the players
            for player_id in self.players:
                await self.players[player_id]['channel'].send(text_data=json.dumps({
                    'type': 'player_addition',
                    'players': [{
                        'id': i,
                        'name': self.players[i]['player'].username,
                        'is_owner': i == self.tournament_owner.id
                    } for i in self.players]
                }))
            self.notify_players_for_user_change = False

    def add_player(self, player, channel):
        if player.id in self.players or self.game_started:
            return
        self.players[player.id] = {
            'channel': channel,
            'player': player
        }
        self.notify_players_for_user_change = True
    
    def remove_player(self, player):
        if player.id in self.players:
            del self.players[player.id]
            # if the player is the last player, remove the tournament
            if len(self.players) == 0:
                self.tournament_deleted = True
                return True
            else:
                self.notify_players_for_user_change = True
                return False
        return False
    
    def start_tournament(self, user):
        if user.id != self.tournament_owner.id:
            return
        self.game_started = True
    
    def end(self):
        pass
    
    def get_players(self):
        return self.players
    
    @sync_to_async
    def change_tournament_ownership(self, tournament_id, user_id):
        if not Tournaments.objects.filter(tournament_id=tournament_id).exists():
            return
        user = User.objects.get(id=user_id)
        tournament = Tournaments.objects.get(tournament_id=tournament_id)
        tournament.created_by = user
        tournament.save()
    
    @sync_to_async
    def get_tournament(self, tournament_id):
        if not Tournaments.objects.filter(tournament_id=tournament_id).exists():
            return None
        return Tournaments.objects.get(tournament_id=tournament_id)

    @sync_to_async
    def remove_tournament(self, tournament_id):
        if not Tournaments.objects.filter(tournament_id=tournament_id).exists():
            return
        tournament = Tournaments.objects.get(tournament_id=tournament_id)
        tournament.delete()
        self.tournament_deleted = True
    
    @sync_to_async
    def get_user(self, user_id):
        return User.objects.get(id=user_id)
    
class TournamentManager:
    tournaments = {}
    started = False
    started_tournaments = []
    
    def __init__(self):
        self.tournaments = {}
        self.started_tournaments = []

    def add_tournament(self, tournament_id):
        self.tournaments[tournament_id] = Tournament({}, self)
        
    def add_player(self, tournament_id, player, channel):
        if tournament_id not in self.tournaments:
            return
        if player.id in self.tournaments[tournament_id].get_players():
            return
        self.tournaments[tournament_id].add_player(player, channel)
        
    def remove_player(self, tournament_id, player):
        if tournament_id not in self.tournaments:
            return
        is_removed = self.tournaments[tournament_id].remove_player(player)
        if is_removed:
            del self.tournaments[tournament_id]
    
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
        for tournament_id in self.tournaments:
            if tournament_id not in self.started_tournaments:
                self.tournaments[tournament_id].start(tournament_id)
                self.started_tournaments.append(tournament_id)
        await asyncio.sleep(0.2)
    
    async def initial_up(self):
        tournaments = list(await self.get_pending_tournaments())
        for tournament in tournaments:
            self.tournaments[tournament.tournament_id] = Tournament({}, self)
            self.tournaments[tournament.tournament_id].start(tournament.tournament_id)
            
    async def start_tournament(self, tournament_id, user):
        if tournament_id not in self.tournaments:
            return
        self.tournaments[tournament_id].start_tournament(user)

    @sync_to_async
    def get_pending_tournaments(self):
        t = Tournaments.objects.filter(status='pending')
        return [i for i in t]
