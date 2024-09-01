import random
import time
from .utils import threaded

class PongGame:
    available_attr = ["ball_color", "map_width", "map_height", "background_color", "skill_ball_freeze", "skill_ball_speed", "powerup_slow_down_opponent", "powerup_speed_up_yourself", "powerup_revert_opponent_controls"]
    time = time.time()
    started = False
    stoped = False
    threshold = 50
    power_up_time = 5319
    is_multiplayer = False

    def __init__(self, data):
        for key in data:
            if key in self.available_attr:
                setattr(self, key, data[key])
        self.opp_score = 0
        self.player_score = 0
        self.width = data["map_width"]
        self.height = data["map_height"]
        self.ball_x = self.width / 2
        self.ball_y = self.height / 2
        self.ball_speed_x = 2.5
        self.ball_speed_y = 2.5
        self.ball_speed_factor = 1.1
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
            "random_power_up_x": self.random_power_up_x,
            "random_power_up_y": self.random_power_up_y
        }
    
    @threaded 
    def start(self):
        self.started = True
        while not self.is_game_over and not self.stoped:
            self.update()
            #make it 60 fps
            time.sleep(1/60)

    def update(self):
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
 
    def render_power_up(self):
        time_now = time.time()
        if time_now - self.time > 15:
            self.time = time_now
            self.random_power_up = random.choice(["powerup_slow_down_opponent", "powerup_speed_up_yourself", "powerup_revert_opponent_controls"])
            self.random_power_up_x = random.randint(0, self.width)
            self.random_power_up_y = random.randint(0, self.height)

    def move_ai(self):
        paddle_speed = self.paddle_speed
        if self.random_power_up == "powerup_slow_down_opponent" and self.is_in_range(threshold=900) and self.last_hitter == "player":
            print("slow down")
            paddle_speed -= 3
        elif self.random_power_up == "powerup_revert_opponent_controls" and self.is_in_range() and self.last_hitter == "player":
            print("revert")
            paddle_speed = paddle_speed
        elif self.random_power_up == "powerup_speed_up_yourself" and self.is_in_range() and self.last_hitter == "ai":
            print("speed up")
            paddle_speed += 5
        if self.ai_y + self.paddle_height / 2 < self.ball_y:
            self.ai_y += paddle_speed
        elif self.ai_y + self.paddle_height / 2 > self.ball_y:
            self.ai_y -= paddle_speed
        print(f"padde_speed_ai: {paddle_speed}")
    
    def ball_collision(self):
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
            self.ball_speed_x = -self.ball_speed_x * self.ball_speed_factor
        if self.ball_x >= self.width - 20 and self.ai_y < self.ball_y < self.ai_y + self.paddle_height:
            if self.is_multiplayer:
                self.last_hitter = "player2"
            else:
                self.last_hitter = "ai"
            self.ball_speed_x = -self.ball_speed_x * self.ball_speed_factor


    def move_player(self, direction):
        paddle_speed = self.paddle_speed
        # print(f"padde_speed: {paddle_speed}")
        print(f"player1_y: {self.player1_y}")
        if self.random_power_up == "powerup_speed_up_yourself" and self.is_in_range() and self.last_hitter == "player":
            print("speed up")
            paddle_speed += 3
        elif self.random_power_up == "powerup_revert_opponent_controls" and self.is_in_range() and self.last_hitter == "ai":
            print("revert")
            paddle_speed = -paddle_speed
        elif self.random_power_up == "powerup_slow_down_opponent" and self.is_in_range(threshold=900) and self.last_hitter == "ai":
            print("slow down")
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
        self.ball_speed_x = 7
        self.ball_speed_y = 7
        self.random_power_up = None
    
    def end_game(self):
        if self.opp_score == 3 or self.player_score == 3:
            self.is_game_over = True