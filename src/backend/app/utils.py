from app.models import ChatRooms, GameRecords
import random
import string

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
