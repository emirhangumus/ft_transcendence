import random
import time
from .utils import threaded
from .consumers import game_rooms
import asyncio

class PongGame:
    available_attr = ["ball_color", "map_width", "map_height", "background_color", "skill_ball_freeze", "skill_ball_speed", "powerup_slow_down_opponent", "powerup_speed_up_yourself", "powerup_revert_opponent_controls"]
    time = time.time()
    started = False
    stoped = False
    threshold = 50
    power_up_time = 5319


    def __init__(self, data, room_id):
        for key in data:
            if key in self.available_attr:
                setattr(self, key, data[key])
        self.opp_score = 0
        self.player_score = 0
        self.width = data["map_width"]
        self.height = data["map_height"]
        self.ball_x = self.width / 2
        self.ball_y = self.height / 2
        self.effected = False
        self.ball_speed_x = 2.5
        self.ball_speed_y = 2.5
        self.ball_speed_factor = 1.1
        self.y_angle = 0
        self.paddle_height = 100
        self.player1_y = self.height // 2 - self.paddle_height // 2
        self.player2_y = self.height // 2 - self.paddle_height // 2
        self.ai_y = self.player1_y
        self.paddle_speed = 7
        self.random_power_up = None
        self.random_power_up_x = None
        self.random_power_up_y = None
        self.is_game_over = False
        self.last_hitter = None
        self.is_multiplayer = data["room_type"] == "multi"
        self.room_id = room_id
        self.how_many_players = 0
        self.state = "waiting_for_players"
        self.start()
        
    def is_in_range(self, threshold=threshold):
        return abs(self.ball_x - self.random_power_up_x) < threshold and abs(self.ball_y - self.random_power_up_y) < threshold

    def get_game_data(self):
        return {
            "ball_x": self.ball_x,
            "ball_y": self.ball_y,
            "player1_y": self.player1_y,
            "player2_y": self.player2_y,
            "ai_y": self.ai_y,
            "opp_score": self.opp_score,
            "player_score": self.player_score,
            "random_power_up": self.random_power_up,
           "random_power_up_x": self.random_power_up_x - (self.threshold / 2) if self.random_power_up else None,
            "random_power_up_y": self.random_power_up_y - (self.threshold / 2) if self.random_power_up else None,
            "threshold": self.threshold,
            "is_multi_player": self.is_multiplayer,
            "state": self.state,
            "customizations": {
                "ball_color": self.ball_color,
                "map_width": self.map_width,
                "map_height": self.map_height,
                "background_color": self.background_color,
                "skill_ball_freeze": self.skill_ball_freeze,
                "skill_ball_speed": self.skill_ball_speed,
                "powerup_slow_down_opponent": self.powerup_slow_down_opponent,
                "powerup_speed_up_yourself": self.powerup_speed_up_yourself,
                "powerup_revert_opponent_controls": self.powerup_revert_opponent_controls
            }
        }
    
    @threaded
    def start(self):
        self.started = True
        while not self.is_game_over and not self.stoped:
            self.update()
            #make it 60 fps
            time.sleep(1/60)

    def reset_power_up(self):
        self.effected = True

    starting_countdown = 3
    def update(self):
        self.how_many_player_here()
        if (self.is_multiplayer and self.how_many_players == 2) or (self.how_many_players == 1 and not self.is_multiplayer):
            if self.state == "waiting_for_players":
                self.state = "game_is_starting"
            if self.state == "playing":
                self.render_power_up()
                self.ball_x += self.ball_speed_x
                self.ball_y += self.ball_speed_y
                self.powerup_checker()
                # Ball collision
                self.ball_collision()
                # Paddle collision
                self.paddle_collision()
                # AI
                if not self.is_multiplayer:
                    self.move_ai()
                # End game
                self.end_game()
            if self.state == "game_is_starting":
                time.sleep(1)
                self.starting_countdown -= 1
                if self.starting_countdown == -1:
                    self.state = "playing"
                    self.starting_countdown = 3
        elif self.how_many_players == 0 or (self.how_many_players == 1 and self.is_multiplayer):
            self.state = "waiting_for_players"

 
    def render_power_up(self):
        time_now = time.time()
        if time_now - self.time > 15:
            self.time = time_now
            self.random_power_up = random.choice(["powerup_slow_down_opponent", "powerup_speed_up_yourself", "powerup_revert_opponent_controls"])
            self.random_power_up_x = random.randint(0, self.width)
            self.random_power_up_y = random.randint(0, self.height)
    
    def how_many_player_here(self):
        if game_rooms[f"game_{self.room_id}"]["player1"] and game_rooms[f"game_{self.room_id}"]["player2"]:
            self.how_many_players = 2
        elif game_rooms[f"game_{self.room_id}"]["player1"]:
            self.how_many_players = 1
        else:
            self.how_many_players = 0


    def move_ai(self):
        paddle_speed = self.paddle_speed
        if self.random_power_up == "powerup_slow_down_opponent" and self.is_in_range(threshold=900) and self.last_hitter == "player":
            print("slow down player")
            paddle_speed -= 5
        elif self.random_power_up == "powerup_revert_opponent_controls" and self.is_in_range() and self.last_hitter == "player":
            print("revert player")
            paddle_speed = paddle_speed
        elif self.random_power_up == "powerup_speed_up_yourself" and self.is_in_range() and self.last_hitter == "ai":
            print("speed up ai")
            paddle_speed += 5
        if self.ai_y + self.paddle_height / 2 < self.ball_y:
            self.ai_y += paddle_speed
        elif self.ai_y + self.paddle_height / 2 > self.ball_y:
            self.ai_y -= paddle_speed
    
    # def ball_hit_place(self):
        # pass

    def ball_collision(self):
        # self.ball_hit_place()
        if self.ball_y <= 0 or self.ball_y >= self.height:
            self.ball_speed_y = -self.ball_speed_y
        if self.ball_x <= 0 or self.ball_x >= self.width:
            self.ball_speed_x = -self.ball_speed_x
            if self.ball_x <= 0:
                self.opp_score += 1
            else:
                self.player_score += 1
            self.reset_ball()

    def paddle_collision(self):
        if self.ball_x <= 20 and self.player1_y < self.ball_y < self.player1_y + self.paddle_height:
            self.last_hitter = "player"
            self.y_angle = (self.player1_y + self.paddle_height / 2 - self.ball_y) / self.paddle_height
            self.ball_speed_y = self.y_angle * 10
            self.ball_speed_x = -self.ball_speed_x * self.ball_speed_factor
        if self.ball_x >= self.width - 20 and self.ai_y < self.ball_y < self.ai_y + self.paddle_height or self.is_multiplayer and self.ball_x >= self.width - 20 and self.player2_y < self.ball_y < self.player2_y + self.paddle_height:
            if self.is_multiplayer:
                self.last_hitter = "player2"
            else:
                self.last_hitter = "ai"
            self.y_angle = (self.ai_y + self.paddle_height / 2 - self.ball_y) / self.paddle_height
            self.ball_speed_y = self.y_angle * 10
            self.ball_speed_x = -self.ball_speed_x * self.ball_speed_factor


    def move_player(self, direction):
        paddle_speed = self.paddle_speed
        if self.random_power_up == "powerup_speed_up_yourself" and self.is_in_range() and self.last_hitter == "player":
            print("speed up player")
            paddle_speed += 3
        elif self.random_power_up == "powerup_revert_opponent_controls" and self.is_in_range() and self.last_hitter == "ai":
            print("revert ai")
            paddle_speed = -paddle_speed
        elif self.random_power_up == "powerup_slow_down_opponent" and self.is_in_range(threshold=900) and self.last_hitter == "ai":
            print("slow down ai")
            paddle_speed -= 3
        if direction == "up" and self.player1_y > 0:
            self.player1_y -= paddle_speed
        if direction == "down" and self.player1_y < self.height - self.paddle_height:
            self.player1_y += paddle_speed

    def move_player2(self, direction):
        self.is_multiplayer = True
        paddle_speed = self.paddle_speed
        if self.random_power_up == "powerup_speed_up_yourself" and self.is_in_range() and self.last_hitter == "ai":
            print("speed up")
            paddle_speed += 3
        elif self.random_power_up == "powerup_revert_opponent_controls" and self.is_in_range() and self.last_hitter == "player":
            print("revert")
            paddle_speed = -paddle_speed
        elif self.random_power_up == "powerup_slow_down_opponent" and self.is_in_range(threshold=900) and self.last_hitter == "player":
            print("slow down")
            paddle_speed -= 3
        if direction == "up" and self.player2_y > 0:
            self.player2_y -= paddle_speed
        if direction == "down" and self.player2_y < self.height - self.paddle_height:
            self.player2_y += paddle_speed

    def powerup_checker(self):
        if self.random_power_up is not None:
            self.power_up_time -= 0.05
        if self.power_up_time <= 0:
            self.random_power_up = None
            self.power_up_time = 6

    def reset_ball(self):
        self.ball_x = self.width / 2
        self.ball_y = self.height / 2
        self.ball_speed_x = 2.5
        self.ball_speed_y = 2.5
        self.random_power_up = None
    
    def end_game(self):
        if self.opp_score == 5 or self.player_score == 5:
            self.is_game_over = True