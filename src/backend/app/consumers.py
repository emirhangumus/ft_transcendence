from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
import json
from .models import ChatRooms, ChatMessages, ChatUsers, Notifications, GameRecords, GameStats, GamePlayers, Friendships, Accounts
from django.contrib.auth.models import User
import time
import asyncio
from .utils import checkAuthForWS
from .managers import NotificationManager, TournamentManager
from .queries.game import updateGameRoom
from .queries.friend import getFriends
from django.db.models import Q
from channels.db import database_sync_to_async

from pprint import pprint

game_rooms = {}
user_room_pairs = {}
notificationManager = NotificationManager()
tournamentManager = TournamentManager()

class ChatConsumer(AsyncWebsocketConsumer):
    user_data = {}
    
    async def connect(self):
        user_data = checkAuthForWS(self.scope)
        if user_data and user_data['valid']:
            self.user_data = user_data
            self.chat_id = self.scope['url_route']['kwargs']['chat_id']
            self.room_group_name = f'chat_{self.chat_id}'

            # Odaya katıl
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )

            # if the user is in user_room_pairs, remove it
            if self.room_group_name in user_room_pairs:
                try:
                    index = user_room_pairs[self.room_group_name].index(user_data['user_id'])
                    del user_room_pairs[self.room_group_name][index]
                except ValueError:
                    pass
            await self.accept()
            user_room_pairs[self.room_group_name] = user_room_pairs.get(self.room_group_name, [])
            user_room_pairs[self.room_group_name].append(user_data['user_id'])

            messages = await self.get_previous_messages(self.chat_id)
            if messages:
                for message in messages:
                    username = await self.get_username(message.sender_id)
                    await self.send(text_data=json.dumps({
                        'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'message': message.message,
                        'username': username,
                        'type': message.type,
                        'payload': message.payload
                    }))

    async def disconnect(self, close_code):
        # Odadan ayrıl
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        if self.room_group_name in user_room_pairs:
            try:
                index = user_room_pairs[self.room_group_name].index(self.user_data['user_id'])
                del user_room_pairs[self.room_group_name][index]
            except ValueError:
                pass

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message')
        username = data.get('username')

        if message and username:
            # Mesajı kaydet ve gruba yayınla
            user, message_obj = await self.save_message(username, self.chat_id, message)
            users_that_are_in_chat = await self.get_users_in_chat(self.chat_id)
            for chat_user in users_that_are_in_chat:
                if chat_user['user_id'] != user.id and not self.is_user_in_channel(chat_user['user_id']):
                    notificationManager.add_notification(chat_user['user_id'], f'{user.username} sent a message to chat {self.chat_id}')
            if user and message_obj:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'created_at': message_obj.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'message': message_obj.message,
                        'username': user.username,
                        't': message_obj
                    }
                )

    async def chat_message(self, event):
        message = event['message']
        username = event['username']
        # Mesajı gönder
        await self.send(text_data=json.dumps({
            'created_at': event['t'].created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'message': message,
            'username': username,
            'type': event['t'].type,
            'payload': event['t'].payload
        }))
        
    def is_user_in_channel(self, user_id):
        for room in user_room_pairs:
            if user_id in user_room_pairs[room]:
                return True
        return False

    @sync_to_async
    def save_message(self, username, chat_id, message):
        room = ChatRooms.objects.get(chat_id=chat_id)
        user = User.objects.get(username=username)
        message_obj = ChatMessages.objects.create(sender=user, room=room, message=message, type='normal')
        return user, message_obj

    @sync_to_async
    def get_previous_messages(self, chat_id):
        room = ChatRooms.objects.get(chat_id=chat_id)
        return list(ChatMessages.objects.filter(room=room).order_by('created_at'))

    @sync_to_async
    def get_username(self, user_id):
        return User.objects.get(id=user_id).username
    
    @sync_to_async
    def get_users_in_chat(self, chat_id):
        room = ChatRooms.objects.get(chat_id=chat_id)
        return list(ChatUsers.objects.filter(room=room).values('user_id'))

class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user_data = checkAuthForWS(self.scope)
        if user_data and user_data['valid']:
            self.game_id = self.scope['url_route']['kwargs']['game_id']
            self.room_group_name = f'game_{self.game_id}'
            
            if self.room_group_name not in game_rooms:
                print("game not found")
                await self.close()
                return
            
            if not game_rooms[self.room_group_name].get('game').get_is_multiplayer() and game_rooms[self.room_group_name].get('player1'):
                print("game is full")
                await self.close()
                return
    
            if game_rooms[self.room_group_name].get('game').get_is_multiplayer() and game_rooms[self.room_group_name].get('player1') and game_rooms[self.room_group_name].get('player2'):
                print("game is full")
                await self.close()
                return
    
            if game_rooms.get(self.room_group_name) and not game_rooms[self.room_group_name].get('player1'):
                game_rooms[self.room_group_name]['player1'] = {
                    'self': self,
                    'user': user_data
                }
            elif game_rooms.get(self.room_group_name) and game_rooms[self.room_group_name].get('player1'):
                game_rooms[self.room_group_name]['player2'] = {
                    'self': self,
                    'user': user_data
                }   

            # Odaya katıl
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
            asyncio.create_task(self.stream_data())
        else:
            await self.close()

    async def disconnect(self, close_code):
        # Odadan ayrıl
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # if the user is in user_room_pairs, remove it
        if self.room_group_name in user_room_pairs:
            try:
                index = user_room_pairs[self.room_group_name].index(self.user_data['user_id'])
                del user_room_pairs[self.room_group_name][index]
            except ValueError:
                pass
        # if the game is not multiplayer, delete the game
        # if the game is multiplayer, remove the player from the game
        if game_rooms.get(self.room_group_name) and not game_rooms[self.room_group_name].get('game').get_is_multiplayer():
            del game_rooms[self.room_group_name]
        elif game_rooms.get(self.room_group_name) and game_rooms[self.room_group_name].get('player1') and self.channel_name == game_rooms[self.room_group_name]['player1']['self'].channel_name:
            del game_rooms[self.room_group_name]['player1']
        elif game_rooms.get(self.room_group_name) and game_rooms[self.room_group_name].get('player2') and self.channel_name == game_rooms[self.room_group_name]['player2']['self'].channel_name:
            del game_rooms[self.room_group_name]['player2']

        # if the game is not multiplayer and there is no player in the game, delete the game            
        if game_rooms.get(self.room_group_name) and not game_rooms[self.room_group_name].get('player1') and not game_rooms[self.room_group_name].get('player2'):
            del game_rooms[self.room_group_name]

    async def receive(self, text_data):
        data = json.loads(text_data)
        
        if data['type'] == 'move':
            if self.channel_name == game_rooms[self.room_group_name]['player1']['self'].channel_name:
                game_rooms[self.room_group_name]['game'].move_player(data['direction'])
            elif self.channel_name == game_rooms[self.room_group_name]['player2']['self'].channel_name:
                game_rooms[self.room_group_name]['game'].move_player2(data['direction'])

    async def stream_data(self):
        report = None
        while True:
            if not game_rooms.get(self.room_group_name):
                break
            current_time = time.time()
            # Generate or fetch your game data to stream
            game_data = {
                'type': 'game_update',
                'payload': {
                    'timestamp': current_time.__str__(),
                    'data': game_rooms[self.room_group_name]['game'].get_game_data()
                    # 'data': self.channel_layer.group_channels[self.room_group_name]
                    # Add other game-related data
                }
            }

            # Broadcast the data to the room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_data',
                    'message': game_data
                }
            )
            
            if not game_rooms[self.room_group_name]['game'].is_game_tournament():
                report = game_rooms[self.room_group_name]['game'].get_final_report()
                if report is not 'final_report_is_already_taken' and report is not 'game_is_not_over':
                    break

            # Wait for a specific interval before sending the next update
            await asyncio.sleep(0.05)  # Adjust the interval as needed | 0.05 is 20 FPS
        
        if report is not None and report is not 'final_report_is_already_taken' and type(report) is dict:
            player1_score = report['player_score']
            player2_score = report['opp_score']
            total_match_time = report['total_match_time']
            heat_map_of_ball = report['heat_map_of_ball']
            loser = None
            winner = None
            if player1_score > player2_score:
                winner = game_rooms[self.room_group_name]['player1']['user']
                loser = game_rooms[self.room_group_name]['player2']['user'] if game_rooms[self.room_group_name]['player2'] else None
            elif player1_score < player2_score:
                winner = game_rooms[self.room_group_name]['player2']['user'] if game_rooms[self.room_group_name]['player2'] else None
                loser = game_rooms[self.room_group_name]['player1']['user']
            
            winner = await self.get_user(winner['user_id'] if winner else 1)
            loser = await self.get_user(loser['user_id'] if loser else 1)

            await self.update_game_player(self.game_id, winner.id)
            await self.update_game_player(self.game_id, loser.id)
            notificationManager.add_notification(loser.id, 'You have lost the game, better luck next time', {"path": "/"}, 'redirection', False)
            notificationManager.add_notification(winner.id, 'You have won the game, congratulations', {"path": "/"}, 'redirection', False)
            await self.update_game_room(self.game_id, player1_score, player2_score, winner, total_match_time)
            await self.update_game_stats(self.game_id, {
                "heatmap": heat_map_of_ball
            })
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_data',
                    'message': {    
                        'type': 'game_over',
                        'payload': report
                    }
                }
            )
            
            
    async def game_data(self, event):
        # Send the game data to WebSocket
        await self.send(text_data=json.dumps(event['message']))
        
    @sync_to_async
    def update_game_room(self, game_id, player1_score, player2_score, winner_id, total_match_time):
        return updateGameRoom(game_id, {
            'player1_score': player1_score,
            'player2_score': player2_score,
            'winner_id': winner_id,
            'total_match_time': total_match_time
        })
        
    @sync_to_async
    def update_game_stats(self, game_id, stats):
        game = GameRecords.objects.get(game_id=game_id)
        game_stats = GameStats.objects.get(game_record=game)
        game_stats.stats = stats
        game_stats.save()
    
    @sync_to_async
    def get_user(self, user_id):
        return User.objects.get(id=user_id)
    
    @sync_to_async
    def update_game_player(self, game_id, player_id):
        game = GameRecords.objects.get(game_id=game_id)
        player = User.objects.get(id=player_id)
        p = GamePlayers.objects.create(game_record=game, player_id=player)
        return p

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.check_notification_manager()
        user_data = checkAuthForWS(self.scope)
        if user_data and user_data['valid']:
            self.user_id = user_data['user_id']
            self.room_group_name = f'notifications_{self.user_id}'
            # Odaya katıl
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()
            notificationManager.register_user(self, self.user_id)
            await self.set_user_status(self.user_id, True)
            user = await self.get_user(self.user_id)
            friends = await self.get_user_friends(self.user_id)
            online_friends = []
            for friend in friends:
                if friend['accounts'].status:
                    online_friends.append(friend)
                notificationManager.add_notification(
                    friend['user'].id,
                    f'{self.user_id} entered!',
                    {
                        "username": user.username,
                        "status": True
                    },
                    'update_status',
                    False
                )
            notifications = await self.get_notifications(self.user_id, 'no')
            notificationManager.add_notification(self.user_id, f'Online friends', { "online_friends": [friend['user'].username for friend in online_friends] }, 'online_friends', False)
            for notification in notifications:
                message = notification.payload.get('message')
                notificationManager.add_notification(self.user_id, message, notification.payload, notification.type, False)
        else:
            await self.close()
            
    def check_notification_manager(self):
        notificationManager.start()
        tournamentManager.start()

    async def disconnect(self, close_code):
        await self.set_user_status(self.user_id, False)
        user = await self.get_user(self.user_id)
        friends = await self.get_user_friends(self.user_id)
        for friend in friends:
            notificationManager.add_notification(friend['user'].id, f'{self.user_id} leaved!', { "username": user.username, "status": False }, 'update_status', False)
        notificationManager.unregister_user(self.user_id)

        # Odadan ayrıl
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
    async def receive(self, text_data):
        data = json.loads(text_data)
        if data['type'] == 'clear':
            await notificationManager.mark_as_read_all(self.user_id)

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
        return list(notifications)
    
    @sync_to_async
    def get_user(self, user_id):
        return User.objects.get(id=user_id)
    
    @sync_to_async
    def set_user_status(self, user_id, status):
        user = Accounts.objects.get(id=user_id)
        user.status = status
        user.save()

    @sync_to_async
    def get_user_friends(self, user_id):
        user = User.objects.get(id=user_id)
        
        # Get the friend relationships involving the user
        friends_ids = Friendships.objects.filter(
            Q(sender=user) | Q(receiver=user),
            status='accepted'
        ).values_list('sender', 'receiver')
        
        # Extract the friend IDs
        friends_ids = [
            friend_id[0] if friend_id[1] == user.id else friend_id[1] 
            for friend_id in friends_ids
        ]
        
        # Get the User objects and their related Accounts in one query
        friend_accounts = Accounts.objects.filter(id__in=friends_ids)
        friend_users = User.objects.filter(id__in=friends_ids)
        
        # Combine the User and Account objects
        friends = [
            {
                'user': friend_user,
                'accounts': friend_account
            }
            for friend_user, friend_account in zip(friend_users, friend_accounts)
        ]
        
        return friends
        
    
class TournamentConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user_data = checkAuthForWS(self.scope)
        if user_data and user_data['valid']:
            self.tournament_id = self.scope['url_route']['kwargs']['tournament_id']
            self.room_group_name = f'tournament_{self.tournament_id}'

            # Odaya katıl
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()
            user = await self.get_user(user_data['user_id'])
            if user:
                self.user_id = user.id
                tournamentManager.add_player(self.tournament_id, user, self)
        else:
            await self.close()

    async def disconnect(self, close_code):
        # Odadan ayrıl
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        user = await self.get_user(self.user_id)
        tournamentManager.remove_player(self.tournament_id, user)

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data['type'] == 'start_tournament':
            user = await self.get_user(self.user_id)
            tournamentManager.start_tournament(self.tournament_id, user)
            
    
    @sync_to_async
    def get_user(self, user_id):
        return User.objects.get(id=user_id)