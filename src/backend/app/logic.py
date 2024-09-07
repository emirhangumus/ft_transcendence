import random
import time
from .utils import threaded
from .consumers import game_rooms
import asyncio


class PongGame:
    customizations = ["ball_color", "map_width", "map_height", "background_color"]
    heat_map_of_ball = []
    time = time.time()
    started = False
    stoped = False
    threshold = 50
    power_up_time = 5319
    final_report_taken = False


    def __init__(self, data, room_id):
        self.ball_color = data["ball_color"]
        self.background_color = data["background_color"]
        self.skill_ball_freeze = data["skill_ball_freeze"]
        self.skill_ball_speed = data["skill_ball_speed"]
        self.powerup_slow_down_opponent = data["powerup_slow_down_opponent"]
        self.powerup_speed_up_yourself = data["powerup_speed_up_yourself"]
        self.powerup_revert_opponent_controls = data["powerup_revert_opponent_controls"]
        self.opp_score = 0
        self.player_score = 0
        self.width = data["map_width"]
        self.height = data["map_height"]
        self.ball_x = self.width / 2
        self.ball_y = self.height / 2
        self.effected = False
        self.ball_speed_x = 5
        self.ball_speed_y = 2.5
        self.ball_speed_factor = 1.1
        self.y_angle = 6
        self.paddle_height = 100
        self.total_match_time = 0
        self.start_time = time.time()
        self.player1_y = self.height // 2 - self.paddle_height // 2
        self.player2_y = self.height // 2 - self.paddle_height // 2
        self.ai_y = self.player1_y
        self.paddle_speed = 12
        self.random_power_up = None
        self.random_power_up_x = None
        self.random_power_up_y = None
        self.is_game_over = False
        self.last_hitter = None
        self.is_multiplayer = data["room_type"] == "multi" or data['room_type'] == "tournament"
        self.is_tournament = data['room_type'] == "tournament"
        self.room_id = room_id
        self.init_available_attr()
        self.how_many_players = 0
        self.state = "waiting_for_players"
        self.start()

    def init_available_attr(self):
        self.available_attr = []
        if self.powerup_slow_down_opponent:
            self.available_attr.append("powerup_slow_down_opponent")
        if self.powerup_speed_up_yourself:
            self.available_attr.append("powerup_speed_up_yourself")
        if self.powerup_revert_opponent_controls:
            self.available_attr.append("powerup_revert_opponent_controls")
        if self.skill_ball_freeze:
            self.available_attr.append("skill_ball_freeze")
        if self.skill_ball_speed:
            self.available_attr.append("skill_ball_speed")

    def is_in_range(self, threshold=threshold):
        return abs(self.ball_x - self.random_power_up_x) < threshold and abs(self.ball_y - self.random_power_up_y) < threshold
    
    def get_final_report(self):
        if self.final_report_taken:
            return 'final_report_is_already_taken'
        if not self.is_game_over:
            return 'game_is_not_over'
        self.final_report_taken = True
        return {
            "opp_score": self.opp_score,
            "player_score": self.player_score,
            "total_match_time": self.total_match_time,
            "winner": "player" if self.player_score > self.opp_score else "opponent",
            "heat_map_of_ball": self.heat_map_of_ball
        }

    def is_game_tournament(self):
        return self.is_tournament

    def get_game_data(self):
        if self.is_game_over:
            return {
                "state": "game_is_over"
            }
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
            "effected": self.effected,
            "customizations": {
                "ball_color": self.ball_color,
                "map_width": self.width,
                "map_height": self.height,
                "background_color": self.background_color,
                "skill_ball_freeze": self.skill_ball_freeze,
                "skill_ball_speed": self.skill_ball_speed,
                "powerup_slow_down_opponent": self.powerup_slow_down_opponent,
                "powerup_speed_up_yourself": self.powerup_speed_up_yourself,
                "powerup_revert_opponent_controls": self.powerup_revert_opponent_controls,
                "skill_ball_freeze": self.skill_ball_freeze,
                "skill_ball_speed": self.skill_ball_speed
            },
            "meta": {
                "how_many_players": self.how_many_players,
                "is_tournament": self.is_tournament,
                "is_multiplayer": self.is_multiplayer
            }
        }
    
    @threaded
    def start(self):
        self.started = True
        heat_map_timer = time.time()
        while not self.is_game_over and not self.stoped:
            self.update()
            
            # every 0.2 seconds update the heat map
            if time.time() - heat_map_timer >= 0.1:
                heat_map_timer = time.time()
                # if its same as the last one dont append
                if len(self.heat_map_of_ball) == 0 or self.heat_map_of_ball[-1] != [int(self.ball_x), int(self.ball_y)]:
                    self.heat_map_of_ball.append([int(self.ball_x), int(self.ball_y)])
                    if len(self.heat_map_of_ball) > 1000:
                        self.heat_map_of_ball.pop(0)
            
            #make it 60 fps
            time.sleep(1/60)
        while not self.final_report_taken:
            time.sleep(0.2)

    def create_power_up(self):
        if len(self.available_attr) > 0:
            self.random_power_up =random.choice(self.available_attr)
            self.random_power_up_x = random.randint(0, self.width)
            self.random_power_up_y = random.randint(0, self.height)
        else:
            return None

    starting_countdown = 3
    def update(self):
        self.how_many_player_here()
        if (self.is_multiplayer and self.how_many_players == 2) or (self.how_many_players == 1 and not self.is_multiplayer):
            if self.state == "waiting_for_players":
                self.state = "game_is_starting"
            if self.state == "playing":
                self.render_power_up()
                if self.skill_ball_freeze and self.random_power_up == "skill_ball_freeze" and self.is_in_range():
                    self.ball_x += 0
                    self.ball_y += 0
                elif self.skill_ball_speed and self.random_power_up == "skill_ball_speed" and self.is_in_range():
                    self.ball_x += self.ball_speed_x * 1.5
                    self.ball_y += self.ball_speed_y * 1.5
                else:
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
            self.effected = True
            self.create_power_up()
    
    def how_many_player_here(self):
        if ('game_' + self.room_id) in game_rooms:
            if game_rooms[f"game_{self.room_id}"]["player1"] and game_rooms[f"game_{self.room_id}"]["player2"]:
                self.how_many_players = 2
            elif game_rooms[f"game_{self.room_id}"]["player1"]:
                self.how_many_players = 1
            else:
                self.how_many_players = 0


    # def move_ai(self):
    #     paddle_speed = self.paddle_speed
    #     if self.random_power_up == "powerup_slow_down_opponent" and self.is_in_range(threshold=900) and self.last_hitter == "player":
    #         paddle_speed = 3
    #     elif self.random_power_up == "powerup_revert_opponent_controls" and self.is_in_range() and self.last_hitter == "player":
    #         paddle_speed = paddle_speed
    #     elif self.random_power_up == "powerup_speed_up_yourself" and self.is_in_range() and self.last_hitter == "ai":
    #         paddle_speed += 15
    #     if self.ai_y + self.paddle_height / 2 < self.ball_y:
    #         self.ai_y += paddle_speed
    #     elif self.ai_y + self.paddle_height / 2 > self.ball_y:
    #         self.ai_y -= paddle_speed
    def move_ai(self):
        paddle_speed = self.paddle_speed

        distance_to_ball = abs(self.ball_x - 20)  # 20, paddle'ın x koordinatı

        max_divisions = 6
        min_divisions = 3
        divisions = max(min_divisions, min(max_divisions, int(self.width / (distance_to_ball + 1))))

        region_height = self.height / divisions

        ball_region = int(self.ball_y / region_height)

        target_y = (ball_region * region_height) + random.randint(0, int(region_height - self.paddle_height))

        if self.ai_y + self.paddle_height / 2 < target_y:
            self.ai_y += paddle_speed / 2
        elif self.ai_y + self.paddle_height / 2 > target_y:
            self.ai_y -= paddle_speed / 2

        if self.ai_y < 0:
            self.ai_y = 0
        elif self.ai_y > self.height - self.paddle_height:
            self.ai_y = self.height - self.paddle_height
    
    # def ball_hit_place(self):
        # pass

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
            self.y_angle = (self.player1_y + self.paddle_height / 2 - self.ball_y) / self.paddle_height
            self.ball_speed_y = self.y_angle * 10
            self.ball_speed_x = -self.ball_speed_x * self.ball_speed_factor
        if self.ball_x >= self.width - 20 and self.ai_y < self.ball_y < self.ai_y + self.paddle_height or self.is_multiplayer and self.ball_x >= self.width - 20 and self.player2_y < self.ball_y < self.player2_y + self.paddle_height:
            if self.is_multiplayer:
                self.last_hitter = "player2"
                self.y_angle = (self.player2_y + self.paddle_height / 2 - self.ball_y) / self.paddle_height
            else:
                self.last_hitter = "ai"
                self.y_angle = (self.ai_y + self.paddle_height / 2 - self.ball_y) / self.paddle_height
            self.ball_speed_y = self.y_angle * 10            
            self.ball_speed_x = -self.ball_speed_x * self.ball_speed_factor


    def move_player(self, direction):
        paddle_speed = self.paddle_speed
        if self.random_power_up == "powerup_speed_up_yourself" and self.is_in_range() and self.last_hitter == "player":
            paddle_speed += 13
        elif self.random_power_up == "powerup_revert_opponent_controls" and self.is_in_range() and self.last_hitter == "ai":
            paddle_speed = -paddle_speed
        elif self.random_power_up == "powerup_slow_down_opponent" and self.is_in_range(threshold=900) and self.last_hitter == "ai":
            paddle_speed -= 3
        if direction == "up" and self.player1_y > 0:
            self.player1_y -= paddle_speed
        if direction == "down" and self.player1_y < self.height - self.paddle_height:
            self.player1_y += paddle_speed

    def move_player2(self, direction):
        self.is_multiplayer = True
        paddle_speed = self.paddle_speed
        if self.random_power_up == "powerup_speed_up_yourself" and self.is_in_range() and self.last_hitter == "ai":
            paddle_speed += 3
        elif self.random_power_up == "powerup_revert_opponent_controls" and self.is_in_range() and self.last_hitter == "player":
            paddle_speed = -paddle_speed
        elif self.random_power_up == "powerup_slow_down_opponent" and self.is_in_range(threshold=900) and self.last_hitter == "player":
            paddle_speed -= 3
        if direction == "up" and self.player2_y > 0:
            self.player2_y -= paddle_speed
        if direction == "down" and self.player2_y < self.height - self.paddle_height:
            self.player2_y += paddle_speed

    def powerup_checker(self):
        if self.random_power_up and self.is_in_range():
            self.effected = False
        if self.random_power_up is not None:
            self.power_up_time -= 0.05
        if self.power_up_time <= 0:
            self.random_power_up = None
            self.power_up_time = 6

    def reset_ball(self):
        self.ball_x = self.width / 2
        self.ball_y = self.height / 2
        self.ball_speed_x = random.choice([-5, -2.5, 2.5, 5])
        self.ball_speed_y = random.choice([-2.5, -1.5, 1.5, 2.5])
        self.random_power_up = None
        self.player1_y = self.height // 2 - self.paddle_height // 2
        if self.is_multiplayer:
            self.player2_y = self.height // 2 - self.paddle_height // 2
        else:
            self.ai_y = self.height // 2 - self.paddle_height // 2
        time.sleep(1)
    
    def end_game(self):
        if self.opp_score == 1 or self.player_score == 1:
            self.total_match_time = time.time() - self.start_time
            self.is_game_over = True
            
    def get_is_multiplayer(self):
        return self.is_multiplayer
    
    