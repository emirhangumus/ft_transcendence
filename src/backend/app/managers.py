import json
from .models import Notifications, Tournaments, ChatUsers, ChatRooms, ChatMessages
import asyncio
from .utils import threaded, synchronized_method
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
import random
import math
from .queries.game import createGameRoom, addPlayerToGameRoom, updateGameRoom
from .models import GameRecords, GameStats

class NotificationManager:
    types = ['normal', 'friend_request', 'match_invite', 'match_result', 'redirection']
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

    @synchronized_method
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
                # remove the notification from the queue
                self.queue[user_id].remove(notification)
        await asyncio.sleep(1)

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
    tournament_ended = False

    section_number = 0
    prepare_fixtures = False
    current_round = 0
    current_available_players = []
    
    fixtures = []
    is_report_taken = False
    
    def __init__(self, players, manager, game_data, tournament_data):
        self.players = players
        self.manager = manager
        self.game_data = game_data
        self.tournament_data = tournament_data
        
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
        while not self.tournament_ended or not self.tournament_deleted:
            if self.tournament_deleted or self.tournament_ended:
                break
            asyncio.run(self.__process())
            if self.tournament_deleted or self.tournament_ended:
                break
        if self.tournament_deleted:
            asyncio.run(self.remove_tournament(self.tournament_id))
        while not self.is_report_taken:
            asyncio.run(self.__wait_for_report_take())

    async def __wait_for_report_take(self):
        await asyncio.sleep(0.2)
        
    def get_final_report(self):
        if self.tournament_ended:
            return {
                'fixtures': self.fixtures,
                'tournament_owner': self.tournament_owner,
                'section_number': self.section_number,
                'tournament_id': self.tournament_id,
                'winner': self.fixtures[-1][0]['winner'],
                'players': [i['player'] for i in self.players.values()]
            }
        return 'tournament_is_not_over'            
    
    async def __init_tournament(self):
        tournament = await self.get_tournament(self.tournament_id)
        self.section_number = math.ceil(math.log2(tournament.player_amount))
        self.tournament_owner = await self.get_user(tournament.created_by_id)
        self.fixtures = [[] for i in range(self.section_number)]
        
    async def __process(self):
        if self.game_started:
            if self.prepare_fixtures:
                await self.__prepare_fixtures(self.current_available_players, self.current_round)
            await self.__is_all_games_finished()
        else:
            await self.__tournament_ownership()
            if self.tournament_deleted:
                return
            await self.__send_player()
            if self.tournament_deleted:
                return
        if self.tournament_ended:
            return
        await asyncio.sleep(0.2)
    
    async def __is_all_games_finished(self):
        from .consumers import notificationManager, game_rooms

        if self.prepare_fixtures:
            return
        for fixture in self.fixtures[self.current_round]:
            result = fixture['game'].get_final_report()
            if result == 'final_report_is_already_taken' or result == 'game_is_not_over':
                continue
            player1_score = result['player_score']
            player2_score = result['opp_score']
            total_match_time = result['total_match_time']
            loser = None
            winner = None
            if player1_score > player2_score:
                winner = game_rooms['game_' + fixture['game_id']]['player1']['user']
                loser = game_rooms['game_' + fixture['game_id']]['player2']['user']
            else:
                winner = game_rooms['game_' + fixture['game_id']]['player2']['user']
                loser = game_rooms['game_' + fixture['game_id']]['player1']['user']
            winner = await self.get_user(winner['user_id'])
            loser = await self.get_user(loser['user_id'])
            notificationManager.add_notification(loser.id, 'You have lost the game, better luck next time', {"path": "/"}, 'redirection', False)
            notificationManager.add_notification(winner.id, 'You won! Wait for the next game!', {"path": "/"}, 'redirection', False)
            fixture['game_result'] = {
                'player1': fixture['player1'],
                'player2': fixture['player2'],
                'total_match_time': total_match_time,
                'player1_score': player1_score,
                'player2_score': player2_score,
                'winner': winner
            }
            fixture['winner'] = winner
            await self.update_game_room(fixture['game_id'], player1_score, player2_score, winner, total_match_time)
            await self.update_game_stats(fixture['game_id'], {
                'heatmap': result['heat_map_of_ball'],
            })
        if all([i['winner'] is not None for i in self.fixtures[self.current_round]]):
            self.current_available_players = {i['winner'].id: i['winner'] for i in self.fixtures[self.current_round]}
            self.current_round += 1
            if self.current_round == self.section_number:
                self.end()
                return
            self.prepare_fixtures = True
    
    async def __prepare_fixtures(self, players, current_round):
        from .logic import PongGame
        from .consumers import game_rooms

        random_players = list(players.keys())
        random.shuffle(random_players)
        
        # initial the first round
        i = 0
        while i < len(random_players):
            player1_id = random_players[i]
            player2_id = random_players[i + 1]
            player1 = await self.get_user(player1_id)
            player2 = await self.get_user(player2_id)
            game_id = await self._createGameRoom(self.game_data)
            await self._addPlayerToGameRoom(game_id, player1)
            await self._addPlayerToGameRoom(game_id, player2)
            self.fixtures[current_round].append({
                'player1': player1,
                'player2': player2,
                'winner': None,
                'game': PongGame(self.game_data, game_id),
                'game_result': None,
                'game_id': game_id
            })
            game_rooms['game_' + game_id] = {
                'game': None,
                'player1': None,
                'player2': None
            }
            game_rooms['game_' + game_id]['game'] = self.fixtures[current_round][-1]['game']
            i += 2
        self.prepare_fixtures = False
        if self.current_round == 0:
            await self.__redirect_players_to_games()
        else:
            await self.__send_game_invite_messages()

    async def __send_game_invite_messages(self):
        from .consumers import notificationManager

        for fixture in self.fixtures[self.current_round]:
            for player in self.players:
                if player == fixture['player1'].id:
                    notificationManager.add_notification(fixture['player1'].id, 'Go next round!', {}, 'normal', False)
                    await self.__claptrap_message(fixture['player1'].id, fixture['game_id'])
                if player == fixture['player2'].id:
                    notificationManager.add_notification(fixture['player2'].id, 'Go next round!', {}, 'normal', False)
                    await self.__claptrap_message(fixture['player2'].id, fixture['game_id'])
    
    async def __claptrap_message(self, userId, gameId):
        t = await self.save_message_claptrap(userId, "TEST", gameId)
        print

    async def __redirect_players_to_games(self):
        for fixture in self.fixtures[self.current_round]:
            for player in self.players:
                if player == fixture['player1'].id or player == fixture['player2'].id:
                    await self.players[player]['channel'].send(text_data=json.dumps({
                        'type': 'game_redirect',
                        'game_id': fixture['game_id']
                    }))
    
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
                    'owner': self.tournament_owner.username,
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
        if len(self.players) != self.tournament_data['player_amount']:
            return
        self.prepare_fixtures = True
        self.game_started = True
        self.current_available_players = self.players
    
    def end(self):
        self.tournament_ended = True
    
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
    
    @sync_to_async
    def _createGameRoom(self, data):
        return createGameRoom(data)
    
    @sync_to_async
    def _addPlayerToGameRoom(self, game_id, player_id):
        return addPlayerToGameRoom(game_id, player_id)
    
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
    def save_message_claptrap(self, user_id, message, game_id):
        # find the user and claptrap room and save the message (claptrap's id is 1)
        bot = User.objects.get(id=1)
        botrooms = ChatUsers.objects.filter(user=bot)
        user = User.objects.get(id=user_id)
        rooms = [i.room for i in botrooms]
        chat_room = ChatUsers.objects.filter(user=user, room__in=rooms).first()
        if chat_room is None:
            return None
        print(chat_room)
        print(chat_room.room)
        message_obj = ChatMessages.objects.create(room=chat_room.room, sender=bot, message="The next game is about to start, good luck!", type="match_invite", payload={"game_id": game_id})
        return user, message_obj

class TournamentManager:
    tournaments = {}
    started = False
    started_tournaments = []
    
    def __init__(self):
        self.tournaments = {}
        self.started_tournaments = []

    def add_tournament(self, tournament_id, game_data, tournament_data):
        self.tournaments[tournament_id] = Tournament({}, self, game_data, tournament_data)
        
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
        from .consumers import notificationManager
        
        for tournament_id in self.tournaments:
            if tournament_id not in self.started_tournaments:
                self.tournaments[tournament_id].start(tournament_id)
                self.started_tournaments.append(tournament_id)
        will_be_removed = []
        for tournament_id in self.tournaments:
            final_report = self.tournaments[tournament_id].get_final_report()
            if final_report != 'tournament_is_not_over':
                players = final_report['players']
                for player in players:
                    notificationManager.add_notification(player.id, 'Tournament has ended, the winner is ' + final_report['winner'].username, {
                        'tournament_id': final_report['tournament_id'],
                        'winner': final_report['winner'].username
                    }, 'normal', True)
                
                await self.save_the_tournament(final_report)
                
                will_be_removed.append(tournament_id)
                
        for tournament_id in will_be_removed:
            del self.tournaments[tournament_id]
        await asyncio.sleep(0.2)
    
    async def initial_up(self):
        tournaments = list(await self.get_pending_tournaments())
        for tournament in tournaments:
            self.tournaments[tournament.tournament_id] = Tournament({}, self, tournament.game_settings, {"player_amount": tournament.player_amount})
            self.tournaments[tournament.tournament_id].start(tournament.tournament_id)
            
    def start_tournament(self, tournament_id, user):
        if tournament_id not in self.tournaments:
            return
        self.tournaments[tournament_id].start_tournament(user)

    @sync_to_async
    def get_pending_tournaments(self):
        t = Tournaments.objects.filter(status='pending')
        return [i for i in t]

    @sync_to_async
    def save_the_tournament(self, tournament):
        t = Tournaments.objects.get(tournament_id=tournament['tournament_id'])
        t.status = 'ended'
        t.winner = tournament['winner']
        t.save()
        # save the who_joined
        for player in tournament['players']:
            t.who_joined.add(player)
        t.save()