from app.models import GameRecords, GamePlayers, GameTypes, GameStats
from app.utils import generateRandomID
from django.contrib.auth.models import User

def createGameRoom(data):
    game_id = generateRandomID('gamerecords')
    game_record = GameRecords.objects.create(game_id=game_id, player1_score=0, player2_score=0, winner_id=None, total_match_time=0)
    game_type = GameTypes.objects.create(game_record=game_record, payload=data)
    game_stat = GameStats.objects.create(game_record=game_record, stats={
        "heatmap": []
    })
    return game_id

def addPlayerToGameRoom(game_id, player):
    game_record = GameRecords.objects.get(game_id=game_id)
    player = GamePlayers.objects.create(game_record=game_record, player_id=player)
    
def updateGameRoom(game_id, data):
    game_record = GameRecords.objects.get(game_id=game_id)
    game_record.player1_score = data['player1_score']
    game_record.player2_score = data['player2_score']
    game_record.winner_id = data['winner_id']
    game_record.total_match_time = data['total_match_time']
    game_record.save()
