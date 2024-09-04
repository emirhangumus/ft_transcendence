from app.models import ChatRooms, GameRecords, Tournaments
import random
import string
import time
from .jwt import validate_access_token
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
import pyotp
import qrcode
from qrcode.image.svg import SvgImage
import io
import os
import math

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
        case 'chatrooms':
            while ChatRooms.objects.filter(chat_id=id).exists():
                id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        case 'gamerecords':
            while GameRecords.objects.filter(game_id=id).exists():
                id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        case 'tournaments':
            while Tournaments.objects.filter(tournament_id=id).exists():
                id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        case _:
            raise ValueError('Invalid lookup')
    return id

def gameTread(self, game):
    while True:
        game.update()
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

def isValidUsername(username: str) -> bool:
    return username.isalnum() and len(username) >= 4 and len(username) <= 30

def generate2FAQRCode(email: str) -> str:
    totp = pyotp.TOTP('base32secret3232')
    totp.now() # => 492039
    data = totp.provisioning_uri(email)
    # Create a QRCode object
    qr = qrcode.QRCode(
        version=1,  # controls the size of the QR Code
        error_correction=qrcode.constants.ERROR_CORRECT_L,  # how much error correction to add
        box_size=10,  # controls how many pixels each “box” of the QR code is
        border=4,  # controls how many boxes thick the border should be
    )

    # Add data to the QR code
    qr.add_data(data)
    qr.make(fit=True)

    # Create an SVG drawing object
    svg_buffer = io.BytesIO()
    qr.make_image(image_factory=SvgImage).save(svg_buffer)

    # Store the SVG content in a variable
    svg_content = svg_buffer.getvalue().decode()
    
    svg_content = svg_content.replace('svg:', '')
    
    return svg_content

def generate_svg_pie_chart(wins, losses, ties):
    total = wins + losses + ties
    if total == 0:
        total = 1  # Avoid division by zero

    win_percentage = wins / total * 100
    loss_percentage = losses / total * 100
    tie_percentage = ties / total * 100

    win_angle = win_percentage * 3.6
    loss_angle = loss_percentage * 3.6
    tie_angle = tie_percentage * 3.6

    def polar_to_cartesian(centerX, centerY, radius, angle_in_degrees):
        angle_in_radians = math.radians(angle_in_degrees)
        return {
            'x': centerX + radius * math.cos(angle_in_radians),
            'y': centerY + radius * math.sin(angle_in_radians)
        }

    centerX, centerY, radius = 150, 150, 100
    large_arc_flag = 1 if win_angle > 180 else 0
    win_end_coords = polar_to_cartesian(centerX, centerY, radius, win_angle)

    svg = f"""
    <svg width="300" height="300" viewBox="0 0 300 300" xmlns="http://www.w3.org/2000/svg">
        <circle cx="{centerX}" cy="{centerY}" r="{radius}" fill="#d3d3d3"/>
        <path d="M {centerX},{centerY} L {centerX+radius}, {centerY} A {radius},{radius} 0 {large_arc_flag},1 {win_end_coords['x']}, {win_end_coords['y']} Z" fill="#00ff00" />
        <path d="M {win_end_coords['x']},{win_end_coords['y']} L {centerX},{centerY} A {radius},{radius} 0 0,1 {centerX+radius}, {centerY} Z" fill="#ff0000" />
        <text x="10" y="20" fill="black">Wins: {win_percentage:.2f}%</text>
        <text x="10" y="40" fill="black">Losses: {loss_percentage:.2f}%</text>
        <text x="10" y="60" fill="black">Ties: {tie_percentage:.2f}%</text>
    </svg>
    """
    return svg
