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
import random

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
    totp = pyotp.TOTP(os.environ.get('2FA_SECRET_KEY'))
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

def validate2FA(code: str) -> bool:
    totp = pyotp.TOTP(os.environ.get('2FA_SECRET_KEY'))
    return totp.verify(code)

def generate_svg_pie_chart(wins, losses, ties):
    total = wins + losses + ties
    if total == 0:
        return ""  # If there's no data, return an empty string to skip rendering the chart

    # Calculate proportions for each segment
    win_percentage = wins / total * 100
    loss_percentage = losses / total * 100
    tie_percentage = ties / total * 100

    win_angle = win_percentage * 3.6  # Convert percentage to degrees (100% -> 360 degrees)
    loss_angle = loss_percentage * 3.6
    tie_angle = tie_percentage * 3.6

    def polar_to_cartesian(centerX, centerY, radius, angle_in_degrees):
        angle_in_radians = math.radians(angle_in_degrees)
        return {
            'x': centerX + radius * math.cos(angle_in_radians),
            'y': centerY + radius * math.sin(angle_in_radians)
        }

    centerX, centerY, radius = 150, 150, 100
    start_coords = {'x': centerX + radius, 'y': centerY}
    
    # SVG starts here
    svg_parts = [f'<svg width="500" height="300" viewBox="0 0 500 300" xmlns="http://www.w3.org/2000/svg">']

    # Full circle background for reference
    svg_parts.append(f'<circle cx="{centerX}" cy="{centerY}" r="{radius}" fill="#d3d3d3"/>')

    current_angle = 0

    # Add Wins slice (Green)
    if wins > 0:
        end_coords = polar_to_cartesian(centerX, centerY, radius, current_angle + win_angle)
        large_arc_flag = 1 if win_angle > 180 else 0
        svg_parts.append(f'<path d="M {centerX},{centerY} L {start_coords["x"]},{start_coords["y"]} A {radius},{radius} 0 {large_arc_flag},1 {end_coords["x"]},{end_coords["y"]} Z" fill="#00ff00" />')
        start_coords = end_coords  # Update the starting point for the next slice
        current_angle += win_angle

    # Add Losses slice (Red)
    if losses > 0:
        end_coords = polar_to_cartesian(centerX, centerY, radius, current_angle + loss_angle)
        large_arc_flag = 1 if loss_angle > 180 else 0
        svg_parts.append(f'<path d="M {centerX},{centerY} L {start_coords["x"]},{start_coords["y"]} A {radius},{radius} 0 {large_arc_flag},1 {end_coords["x"]},{end_coords["y"]} Z" fill="#ff0000" />')
        start_coords = end_coords
        current_angle += loss_angle

    # Add Ties slice (Yellow)
    if ties > 0:
        end_coords = polar_to_cartesian(centerX, centerY, radius, current_angle + tie_angle)
        large_arc_flag = 1 if tie_angle > 180 else 0
        svg_parts.append(f'<path d="M {centerX},{centerY} L {start_coords["x"]},{start_coords["y"]} A {radius},{radius} 0 {large_arc_flag},1 {end_coords["x"]},{end_coords["y"]} Z" fill="#ffff00" />')

    # Add the legend with color boxes and percentages next to the chart
    legend_start_x = 320  # Legend x position
    legend_start_y = 80   # Legend y position
    box_size = 15         # Size of color boxes

    # Wins legend
    svg_parts.append(f'<rect x="{legend_start_x}" y="{legend_start_y}" width="{box_size}" height="{box_size}" fill="#00ff00"/>')
    svg_parts.append(f'<text x="{legend_start_x + 20}" y="{legend_start_y + 12}" fill="black">Wins: {win_percentage:.2f}%</text>')

    # Losses legend
    svg_parts.append(f'<rect x="{legend_start_x}" y="{legend_start_y + 30}" width="{box_size}" height="{box_size}" fill="#ff0000"/>')
    svg_parts.append(f'<text x="{legend_start_x + 20}" y="{legend_start_y + 42}" fill="black">Losses: {loss_percentage:.2f}%</text>')

    # Ties legend
    svg_parts.append(f'<rect x="{legend_start_x}" y="{legend_start_y + 60}" width="{box_size}" height="{box_size}" fill="#ffff00"/>')
    svg_parts.append(f'<text x="{legend_start_x + 20}" y="{legend_start_y + 72}" fill="black">Ties: {tie_percentage:.2f}%</text>')

    svg_parts.append('</svg>')

    return ''.join(svg_parts)


def generate_svg_heatmap_with_dynamic_size(ball_locations, field_width=400, field_height=400, grid_size=20):
    """
    Generates an SVG heatmap based on ball location data with dynamic field dimensions.

    :param ball_locations: A list of (x, y) tuples representing ball positions.
    :param field_width: The width of the field in pixels.
    :param field_height: The height of the field in pixels.
    :param grid_size: The size of each grid cell in pixels.
    :return: An SVG string representing the heatmap.
    """
    # Initialize the grid
    num_x_cells = field_width // grid_size
    num_y_cells = field_height // grid_size
    grid = [[0 for _ in range(num_x_cells)] for _ in range(num_y_cells)]

    # Populate the grid with counts of ball locations
    for (x, y) in ball_locations:
        grid_x = min(x // grid_size, num_x_cells - 1)
        grid_y = min(y // grid_size, num_y_cells - 1)
        grid[grid_y][grid_x] += 1

    # Find the max count for normalization
    max_count = max(max(row) for row in grid) if ball_locations else 1

    def count_to_color(count):
        """Convert count to a color intensity (red) based on the maximum count."""
        intensity = int((count / max_count) * 255)
        return f"rgb({intensity}, 0, 0)"  # Red intensity

    # Start building the SVG
    svg_parts = []
    svg_parts.append(f'<svg width="{field_width}" height="{field_height}" xmlns="http://www.w3.org/2000/svg">')

    # Generate the grid cells with varying color intensity
    for row_idx, row in enumerate(grid):
        for col_idx, count in enumerate(row):
            x_pos = col_idx * grid_size
            y_pos = row_idx * grid_size
            color = count_to_color(count)
            svg_parts.append(f'<rect x="{x_pos}" y="{y_pos}" width="{grid_size}" height="{grid_size}" fill="{color}" />')

    # Close the SVG tag
    svg_parts.append('</svg>')

    return ''.join(svg_parts)
