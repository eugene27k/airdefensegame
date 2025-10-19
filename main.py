import importlib
import math
import random
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

if importlib.util.find_spec("pygame") is None:
    sys.stderr.write(
        "Pygame is required to run Air Defense Simulator.\n"
        "Install dependencies with 'pip install -r requirements.txt' and try again.\n"
    )
    sys.exit(1)

import pygame

# Global scale to boost resolution while keeping aspect ratio
SCALE = 1.5

# Screen configuration
SCREEN_WIDTH = int(960 * SCALE)
SCREEN_HEIGHT = int(720 * SCALE)
FPS = 60

# Radar/base configuration
RADAR_RADIUS = int(260 * SCALE)
BASE_POSITION = pygame.Vector2(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
BASE_RADIUS = int(40 * SCALE)

# Support car positions relative to base
CAR_OFFSETS = [
    pygame.Vector2(-220 * SCALE, 160 * SCALE),
    pygame.Vector2(0, -260 * SCALE),
    pygame.Vector2(220 * SCALE, 160 * SCALE),
]

TARGET_SPAWN_INTERVAL = 2.2
MAX_TARGETS = 8

MISSILE_SPEED = 280 * 1.1
MISSILE_LOCK_STRENGTH = 0.12

TARGET_TYPES = {
    "Drone": {
        "color": (140, 200, 255),
        "speed": (70, 120),
        "score": 75,
    },
    "Missile": {
        "color": (255, 120, 120),
        "speed": (120, 180),
        "score": 140,
    },
}

BACKGROUND_COLOR = (12, 22, 32)
RADAR_RING_COLOR = (40, 120, 120)
RADAR_SWEEP_COLOR = (50, 180, 160)
UI_TEXT_COLOR = (210, 220, 220)
WARNING_TEXT_COLOR = (255, 100, 100)
SUCCESS_TEXT_COLOR = (120, 220, 120)

LEVEL_TARGET_COUNT = 20
LEVEL_COMPLETE_PAUSE = 3.0


@dataclass
class Target:
    position: pygame.Vector2
    velocity: pygame.Vector2
    target_type: str
    heading: float
    alive: bool = True

    def update(self, dt: float) -> None:
        if not self.alive:
            return
        self.position += self.velocity * dt
        self.heading = math.degrees(math.atan2(self.velocity.y, self.velocity.x))

    def draw(self, surface: pygame.Surface) -> None:
        color = TARGET_TYPES[self.target_type]["color"]
        pygame.draw.circle(surface, color, self.position, int(7 * SCALE))
        # Draw heading indicator line
        direction = pygame.Vector2(math.cos(math.radians(self.heading)), math.sin(math.radians(self.heading)))
        end_pos = self.position + direction * (18 * SCALE)
        pygame.draw.line(surface, color, self.position, end_pos, int(2 * SCALE))


@dataclass
class Missile:
    position: pygame.Vector2
    velocity: pygame.Vector2
    source_index: int
    target: Optional[Target]
    active: bool = True

    def update(self, dt: float) -> None:
        if not self.active:
            return
        if self.target is None or not self.target.alive:
            # No target to chase, coast forward but fade out quickly
            self.position += self.velocity * dt
            self.active = False
            return

        desired_direction = (self.target.position - self.position)
        if desired_direction.length_squared() > 0:
            desired_direction = desired_direction.normalize()
            # Adjust current velocity direction gradually to simulate locking
            current_direction = self.velocity.normalize() if self.velocity.length_squared() > 0 else desired_direction
            new_direction = current_direction.lerp(desired_direction, MISSILE_LOCK_STRENGTH)
            if new_direction.length_squared() > 0:
                new_direction = new_direction.normalize()
            self.velocity = new_direction * MISSILE_SPEED

        self.position += self.velocity * dt

    def draw(self, surface: pygame.Surface) -> None:
        missile_color = (255, 255, 120)
        pygame.draw.circle(surface, missile_color, self.position, int(5 * SCALE))
        tail_length = 12 * SCALE
        tail = self.position - self.velocity.normalize() * tail_length if self.velocity.length_squared() else self.position
        pygame.draw.line(surface, missile_color, self.position, tail, int(2 * SCALE))


@dataclass
class SupportCar:
    position: pygame.Vector2
    index: int
    cool_down: float = 0.0

    def draw(self, surface: pygame.Surface, ready: bool, selected_target: Optional[Target]) -> None:
        target_active = selected_target is not None and selected_target.alive
        car_color = (90, 180, 90) if ready else (70, 90, 70)
        car_size = pygame.Vector2(60 * SCALE, 36 * SCALE)
        car_rect = pygame.Rect(0, 0, int(car_size.x), int(car_size.y))
        car_rect.center = self.position
        pygame.draw.rect(surface, car_color, car_rect, border_radius=int(8 * SCALE))

        left_wheel_pos = self.position + pygame.Vector2(-20 * SCALE, 18 * SCALE)
        right_wheel_pos = self.position + pygame.Vector2(20 * SCALE, 18 * SCALE)
        pygame.draw.circle(surface, (40, 40, 40), left_wheel_pos, int(6 * SCALE))
        pygame.draw.circle(surface, (40, 40, 40), right_wheel_pos, int(6 * SCALE))

        # Ukrainian flag mounted on the side of the vehicle
        flag_width = 22 * SCALE
        flag_height = 14 * SCALE
        flag_rect = pygame.Rect(0, 0, int(flag_width), int(flag_height))
        flag_rect.midright = (car_rect.centerx + car_size.x / 2 + flag_width * 0.2, car_rect.centery - car_size.y * 0.3)
        pygame.draw.rect(surface, (0, 91, 187), flag_rect)
        bottom_rect = pygame.Rect(flag_rect)
        bottom_rect.height //= 2
        bottom_rect.top = flag_rect.top + flag_rect.height // 2
        pygame.draw.rect(surface, (255, 213, 0), bottom_rect)

        # Turret base
        turret_rect = pygame.Rect(0, 0, int(26 * SCALE), int(14 * SCALE))
        turret_rect.center = self.position + pygame.Vector2(0, -car_size.y * 0.25)
        if target_active and ready:
            turret_color = (160, 230, 160)
        elif target_active:
            turret_color = (120, 200, 120)
        else:
            turret_color = (100, 150, 100)
        pygame.draw.rect(surface, turret_color, turret_rect, border_radius=int(6 * SCALE))

        # Turret barrel orientation
        if target_active:
            direction = (selected_target.position - pygame.Vector2(turret_rect.center))
            if direction.length_squared() > 0:
                direction = direction.normalize()
        else:
            direction = pygame.Vector2(0, -1)

        barrel_length = 32 * SCALE
        barrel_start = pygame.Vector2(turret_rect.center)
        barrel_end = barrel_start + direction * barrel_length
        barrel_color = (240, 240, 220) if target_active else (170, 170, 160)
        pygame.draw.line(surface, barrel_color, barrel_start, barrel_end, int(4 * SCALE))


class AirDefenseGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Air Defense Simulator")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", int(20 * SCALE))
        self.big_font = pygame.font.SysFont("consolas", int(32 * SCALE), bold=True)
        self.title_font = pygame.font.SysFont("consolas", int(48 * SCALE), bold=True)
        self.subtitle_font = pygame.font.SysFont("consolas", int(28 * SCALE))
        self.reset()
        self.show_intro()

    def reset(self) -> None:
        self.targets: List[Target] = []
        self.missiles: List[Missile] = []
        self.cars: List[SupportCar] = [SupportCar(BASE_POSITION + offset, idx) for idx, offset in enumerate(CAR_OFFSETS, start=1)]
        self.spawn_timer = TARGET_SPAWN_INTERVAL
        self.selected_target: Optional[Target] = None
        self.score = 0
        self.lives = 5
        self.elapsed = 0.0
        self.game_over = False
        self.level = 1
        self.targets_destroyed = 0
        self.enemy_speed_multiplier = 1.0
        self.score_multiplier = 1
        self.level_complete = False
        self.level_transition_timer = 0.0
        self.lock_timer = 0.0
        self.apply_level_parameters()

    def apply_level_parameters(self) -> None:
        self.enemy_speed_multiplier = 1.0 + 0.05 * (self.level - 1)
        self.score_multiplier = 2 ** (self.level - 1)

    def start_level_complete(self) -> None:
        self.level_complete = True
        self.level_transition_timer = LEVEL_COMPLETE_PAUSE
        self.selected_target = None
        self.lock_timer = 0.0
        for target in self.targets:
            target.alive = False
        for missile in self.missiles:
            missile.active = False

    def advance_level(self) -> None:
        self.level += 1
        self.level_complete = False
        self.level_transition_timer = 0.0
        self.targets_destroyed = 0
        self.apply_level_parameters()
        self.spawn_timer = TARGET_SPAWN_INTERVAL
        self.targets.clear()
        self.missiles.clear()
        self.selected_target = None
        self.lock_timer = 0.0

    def show_intro(self) -> None:
        intro_duration = 2.0
        elapsed = 0.0
        fade_color = (20, 40, 60)
        skip = False
        while elapsed < intro_duration and not skip:
            dt = self.clock.tick(FPS) / 1000.0
            elapsed += dt
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    skip = True
            self.screen.fill(fade_color)

            lines = [
                (self.subtitle_font, "Divanne GameDev Presents", UI_TEXT_COLOR),
                (self.title_font, "Air Defence Ukraine", SUCCESS_TEXT_COLOR),
                (self.subtitle_font, "#standwithUkraine", UI_TEXT_COLOR),
            ]

            spacing = int(16 * SCALE)
            total_height = sum(font.size(text)[1] for font, text, _ in lines) + spacing * (len(lines) - 1)
            current_y = SCREEN_HEIGHT // 2 - total_height // 2

            for font, text, color in lines:
                text_surface = font.render(text, True, color)
                rect = text_surface.get_rect(center=(SCREEN_WIDTH // 2, current_y + text_surface.get_height() // 2))
                self.screen.blit(text_surface, rect)
                current_y += text_surface.get_height() + spacing

            pygame.display.flip()

    def spawn_target(self) -> None:
        if len(self.targets) >= MAX_TARGETS:
            return
        target_type = random.choice(list(TARGET_TYPES.keys()))
        speed_range = TARGET_TYPES[target_type]["speed"]
        speed = random.uniform(*speed_range) * self.enemy_speed_multiplier

        angle = random.uniform(0, 360)
        spawn_distance = RADAR_RADIUS + 90 * SCALE
        spawn_pos = BASE_POSITION + pygame.Vector2(spawn_distance, 0).rotate(angle)

        # Determine if target aims for base or passes by
        if random.random() < 0.65:
            destination = BASE_POSITION + pygame.Vector2(
                random.uniform(-40 * SCALE, 40 * SCALE),
                random.uniform(-40 * SCALE, 40 * SCALE),
            )
        else:
            drift_angle = angle + random.uniform(-60, 60)
            destination = BASE_POSITION + pygame.Vector2(RADAR_RADIUS, 0).rotate(drift_angle)

        direction = (destination - spawn_pos)
        if direction.length_squared() == 0:
            direction = pygame.Vector2(1, 0)
        velocity = direction.normalize() * speed

        heading = math.degrees(math.atan2(velocity.y, velocity.x))
        self.targets.append(Target(spawn_pos, velocity, target_type, heading))

    def handle_input(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.key == pygame.K_r and self.game_over:
                    self.reset()
                if event.key in (pygame.K_1, pygame.K_2, pygame.K_3) and not self.game_over and not self.level_complete:
                    self.command_car(event.key - pygame.K_0)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not self.game_over and not self.level_complete:
                self.select_target(pygame.mouse.get_pos())

    def select_target(self, mouse_pos: Tuple[int, int]) -> None:
        mouse_vec = pygame.Vector2(mouse_pos)
        closest_target = None
        closest_distance = 9999
        for target in self.targets:
            if not target.alive:
                continue
            distance = mouse_vec.distance_to(target.position)
            if distance < 20 and distance < closest_distance:
                closest_target = target
                closest_distance = distance
        if closest_target:
            self.selected_target = closest_target
            self.lock_timer = 0.0

    def command_car(self, car_index: int) -> None:
        if self.level_complete:
            return
        if self.selected_target is None or not self.selected_target.alive:
            return
        if car_index < 1 or car_index > len(self.cars):
            return
        car = self.cars[car_index - 1]
        if car.cool_down > 0:
            return

        # Launch missile
        direction = (self.selected_target.position - car.position)
        if direction.length_squared() == 0:
            direction = pygame.Vector2(1, 0)
        velocity = direction.normalize() * MISSILE_SPEED
        missile = Missile(position=car.position.copy(), velocity=velocity, source_index=car_index, target=self.selected_target)
        self.missiles.append(missile)
        car.cool_down = 1.8

    def update_entities(self, dt: float) -> None:
        for target in self.targets:
            target.update(dt)

        for missile in self.missiles:
            missile.update(dt)

        for car in self.cars:
            car.cool_down = max(0.0, car.cool_down - dt)

        # Collision detection
        for missile in self.missiles:
            if not missile.active or missile.target is None:
                continue
            if missile.target.alive and missile.position.distance_to(missile.target.position) < 12 * SCALE:
                missile.active = False
                missile.target.alive = False
                self.score += TARGET_TYPES[missile.target.target_type]["score"] * self.score_multiplier
                if not self.level_complete:
                    self.targets_destroyed += 1
                    if self.targets_destroyed >= LEVEL_TARGET_COUNT:
                        self.start_level_complete()

        # Base collision
        for target in self.targets:
            if target.position.distance_to(BASE_POSITION) < BASE_RADIUS:
                target.alive = False
                self.lives -= 1
                if self.lives <= 0:
                    self.game_over = True

        # Remove targets that escape radar bounds
        for target in self.targets:
            if target.position.distance_to(BASE_POSITION) > RADAR_RADIUS + 140 * SCALE:
                target.alive = False

        # Clear selection if the chosen target has been eliminated or escaped
        if self.selected_target and not self.selected_target.alive:
            self.selected_target = None

        self.targets = [target for target in self.targets if target.alive]
        self.missiles = [missile for missile in self.missiles if missile.active]

    def update(self, dt: float) -> None:
        if self.game_over:
            return

        if self.selected_target and self.selected_target.alive:
            self.lock_timer += dt
        else:
            self.lock_timer = 0.0

        if self.level_complete:
            self.level_transition_timer -= dt
            if self.level_transition_timer <= 0:
                self.advance_level()
            return
        self.elapsed += dt
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_target()
            self.spawn_timer = random.uniform(TARGET_SPAWN_INTERVAL * 0.6, TARGET_SPAWN_INTERVAL * 1.3)

        self.update_entities(dt)

    def draw_radar(self, surface: pygame.Surface, sweep_angle: float) -> None:
        ring_width = max(1, int(2 * SCALE))
        pygame.draw.circle(surface, RADAR_RING_COLOR, BASE_POSITION, RADAR_RADIUS, ring_width)
        pygame.draw.circle(surface, RADAR_RING_COLOR, BASE_POSITION, BASE_RADIUS, max(1, int(1 * SCALE)))
        for ring in range(1, 4):
            pygame.draw.circle(surface, (30, 80, 80), BASE_POSITION, RADAR_RADIUS * ring / 4, max(1, int(SCALE)))

        # Sweep line
        sweep_direction = pygame.Vector2(RADAR_RADIUS, 0).rotate(sweep_angle)
        pygame.draw.line(surface, RADAR_SWEEP_COLOR, BASE_POSITION, BASE_POSITION + sweep_direction, max(1, int(2 * SCALE)))

        # Crosshair lines
        crosshair_width = max(1, int(SCALE))
        pygame.draw.line(surface, (30, 70, 70), (BASE_POSITION.x - RADAR_RADIUS, BASE_POSITION.y), (BASE_POSITION.x + RADAR_RADIUS, BASE_POSITION.y), crosshair_width)
        pygame.draw.line(surface, (30, 70, 70), (BASE_POSITION.x, BASE_POSITION.y - RADAR_RADIUS), (BASE_POSITION.x, BASE_POSITION.y + RADAR_RADIUS), crosshair_width)

    def draw_ui(self) -> None:
        info_lines = [
            f"Level: {self.level}",
            f"Score: {self.score}",
            f"Lives: {self.lives}",
            f"Contacts: {len(self.targets)}",
            f"Destroyed: {self.targets_destroyed}/{LEVEL_TARGET_COUNT}",
            "Click to select target",
            "Press 1/2/3 to launch",
        ]
        hud_x = int(24 * SCALE)
        hud_y = int(24 * SCALE)
        line_height = int(28 * SCALE)
        for i, line in enumerate(info_lines):
            text_surface = self.font.render(line, True, UI_TEXT_COLOR)
            self.screen.blit(text_surface, (hud_x, hud_y + i * line_height))

        if self.selected_target and self.selected_target.alive:
            selected_text = self.font.render("Target locked", True, SUCCESS_TEXT_COLOR)
            self.screen.blit(selected_text, (hud_x, hud_y + len(info_lines) * line_height))

        if self.game_over:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            self.screen.blit(overlay, (0, 0))
            game_over_text = self.big_font.render("Mission Failed", True, WARNING_TEXT_COLOR)
            prompt_text = self.font.render("Press R to restart", True, UI_TEXT_COLOR)
            self.screen.blit(game_over_text, game_over_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20 * SCALE)))
            self.screen.blit(prompt_text, prompt_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20 * SCALE)))
        elif self.level_complete:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 30, 0, 140))
            self.screen.blit(overlay, (0, 0))
            complete_text = self.big_font.render("Mission Complete", True, SUCCESS_TEXT_COLOR)
            next_level_text = self.font.render(f"Level {self.level + 1} incoming", True, UI_TEXT_COLOR)
            self.screen.blit(complete_text, complete_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20 * SCALE)))
            self.screen.blit(next_level_text, next_level_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20 * SCALE)))

    def draw_entities(self) -> None:
        # Draw support cars
        active_target = self.selected_target if self.selected_target and self.selected_target.alive else None
        for idx, car in enumerate(self.cars, start=1):
            ready = car.cool_down <= 0 and not self.game_over
            car.draw(self.screen, ready, active_target)
            label = self.font.render(str(idx), True, UI_TEXT_COLOR)
            self.screen.blit(label, label.get_rect(center=car.position + pygame.Vector2(0, -30 * SCALE)))

        # Draw base commander car
        pygame.draw.circle(self.screen, (70, 130, 160), BASE_POSITION, BASE_RADIUS)
        pygame.draw.circle(self.screen, (30, 60, 90), BASE_POSITION, BASE_RADIUS, max(2, int(4 * SCALE)))

        # Draw radar targets
        for target in self.targets:
            target.draw(self.screen)

        # Draw missiles
        for missile in self.missiles:
            missile.draw(self.screen)

        # Draw selection indicator
        if active_target:
            pygame.draw.circle(self.screen, (255, 255, 255), active_target.position, int(16 * SCALE), max(1, int(SCALE)))
            self.draw_lock_animation(active_target)

    def draw_lock_animation(self, target: Target) -> None:
        if not target.alive:
            return
        pulse = math.sin(self.lock_timer * 6) * (4 * SCALE)
        base_radius = 24 * SCALE
        for ring_index in range(2):
            radius = base_radius + ring_index * 8 * SCALE + pulse
            color = (160 + ring_index * 40, 255, 200)
            pygame.draw.circle(self.screen, color, target.position, int(radius), max(1, int(SCALE)))

        for quadrant in range(4):
            angle = (self.lock_timer * 180) + quadrant * 90
            inner = target.position + pygame.Vector2(12 * SCALE, 0).rotate(angle)
            outer = target.position + pygame.Vector2(base_radius + pulse + 8 * SCALE, 0).rotate(angle)
            pygame.draw.line(self.screen, (120, 255, 200), inner, outer, max(1, int(2 * SCALE)))

    def draw(self, sweep_angle: float) -> None:
        self.screen.fill(BACKGROUND_COLOR)
        self.draw_radar(self.screen, sweep_angle)
        self.draw_entities()
        self.draw_ui()
        pygame.display.flip()

    def run(self) -> None:
        sweep_angle = 0.0
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            sweep_angle = (sweep_angle + dt * 120) % 360

            self.handle_input()
            self.update(dt)
            self.draw(sweep_angle)


def main() -> None:
    game = AirDefenseGame()
    game.run()


if __name__ == "__main__":
    main()
