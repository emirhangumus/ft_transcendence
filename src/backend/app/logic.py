import random

class PongGame:
    available_attr = ["ball_color", "map_width", "map_height", "background_color", "skill_ball_freeze", "skill_ball_speed", "powerup_slow_down_opponent", "powerup_speed_up_yourself", "powerup_revert_opponent_controls"]

    def __init__(self, data):
        for key in data:
            if key in self.available_attr:
                setattr(self, key, data[key])
        self.opp_score = 0
        self.player_score = 0
        self.width = data.map_width
        self.height = data.map_height
        self.ball_x = self.width // 2
        self.ball_y = self.height // 2
        self.ball_speed_x = 7
        self.ball_speed_y = 7
        self.paddle_height = 100
        self.player_y = self.height // 2 - self.paddle_height // 2
        self.ai_y = self.player_y
        self.paddle_speed = 7

    def render_power_up(self):
        power_up = random.choice(["skill_ball_freeze", "skill_ball_speed", "powerup_slow_down_opponent", "powerup_speed_up_yourself", "powerup_revert_opponent_controls"])
        return power_up

    def update(self):
        self.ball_x += self.ball_speed_x
        self.ball_y += self.ball_speed_y

        if self.ball_y <= 0 or self.ball_y >= self.height:
            self.ball_speed_y = -self.ball_speed_y

        if self.ball_x <= 0 or self.ball_x >= self.width:
            self.ball_speed_x = -self.ball_speed_x
            if self.ball_x <= 0:
                self.opp_score += 1
            else:
                self.player_score += 1
            self.reset_ball()

        if self.ball_x <= 20 and self.player_y < self.ball_y < self.player_y + self.paddle_height:
            self.ball_speed_x = -self.ball_speed_x

        if self.ball_x >= self.width - 20 and self.ai_y < self.ball_y < self.ai_y + self.paddle_height:
            self.ball_speed_x = -self.ball_speed_x

        if self.ai_y + self.paddle_height / 2 < self.ball_y:
            self.ai_y += self.paddle_speed
        elif self.ai_y + self.paddle_height / 2 > self.ball_y:
            self.ai_y -= self.paddle_speed

    def move_player(self, direction):
        if direction == "up" and self.player_y > 0:
            self.player_y -= self.paddle_speed
        if direction == "down" and self.player_y < self.height - self.paddle_height:
            self.player_y += self.paddle_speed

    def reset_ball(self):
        self.ball_x = self.width // 2
        self.ball_y = self.height // 2
