import random
import time
import threading

def threaded(fn):
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
        return thread
    return wrapper

class PongGame:
    available_attr = ["ball_color", "map_width", "map_height", "background_color", "skill_ball_freeze", "skill_ball_speed", "powerup_slow_down_opponent", "powerup_speed_up_yourself", "powerup_revert_opponent_controls"]
    time = time.time()
    started = False

    def __init__(self, data):
        for key in data:
            if key in self.available_attr:
                setattr(self, key, data[key])
        self.opp_score = 0
        self.player_score = 0
        self.width = data["map_width"]
        self.height = data["map_height"]
        self.ball_x = self.width // 2
        self.ball_y = self.height // 2
        self.ball_speed_x = 7
        self.ball_speed_y = 7
        self.ball_speed_factor = 1.1
        self.paddle_height = 100
        self.player_y = self.height // 2 - self.paddle_height // 2
        self.ai_y = self.player_y
        self.paddle_speed = 7
        self.random_power_up = None
        self.random_power_up_x = None
        self.random_power_up_y = None
        self.is_game_over = False
        self.start()
        
    def get_game_data(self):
        return {
            "ball_x": self.ball_x,
            "ball_y": self.ball_y,
            "player_y": self.player_y,
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
        while not self.is_game_over:
            self.update()
            print("thread, ", self.ball_x, self.ball_y)
            time.sleep(0.05)

    def update(self):
        self.render_power_up()
        self.ball_x += self.ball_speed_x
        self.ball_y += self.ball_speed_y
        # Ball collision
        self.ball_collision()
        # Paddle collision
        self.paddle_collision()
        # AI
        self.move_ai()
        # End game
        self.end_game()
 
    def render_power_up(self):
        time_now = time.time()
        if time_now - self.time > 30:
            self.time = time_now
            self.random_power_up = random.choice(["powerup_slow_down_opponent", "powerup_speed_up_yourself", "powerup_revert_opponent_controls"])
            self.random_power_up_x = random.randint(0, self.width)
            self.random_power_up_y = random.randint(0, self.height)

    def move_ai(self):
        paddle_speed = self.paddle_speed
        if self.random_power_up == "powerup_slow_down_opponent":
            paddle_speed -= 3
        if self.ai_y + self.paddle_height / 2 < self.ball_y:
            self.ai_y += paddle_speed
        elif self.ai_y + self.paddle_height / 2 > self.ball_y:
            self.ai_y -= paddle_speed
    
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
        if self.ball_x <= 20 and self.player_y < self.ball_y < self.player_y + self.paddle_height:
            self.ball_speed_x = -self.ball_speed_x * self.ball_speed_factor
        if self.ball_x >= self.width - 20 and self.ai_y < self.ball_y < self.ai_y + self.paddle_height:
            self.ball_speed_x = -self.ball_speed_x * self.ball_speed_factor


    def move_player(self, direction):
        paddle_speed = self.paddle_speed
        if self.random_power_up == "powerup_speed_up_yourself":
            paddle_speed += 3
        if direction == "up" and self.player_y > 0:
            self.player_y -= paddle_speed
        if direction == "down" and self.player_y < self.height - self.paddle_height:
            self.player_y += paddle_speed

    def reset_ball(self):
        self.ball_x = self.width // 2
        self.ball_y = self.height // 2
        self.ball_speed_x = 7
        self.ball_speed_y = 7
    
    def end_game(self):
        if self.opp_score == 3 or self.player_score == 3:
            self.is_game_over = True