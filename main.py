import math
import random
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame

# Screen configuration
SCREEN_WIDTH = 960
SCREEN_HEIGHT = 720
FPS = 60

# Radar/base configuration
RADAR_RADIUS = 260
BASE_POSITION = pygame.Vector2(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
BASE_RADIUS = 40

# Support car positions relative to base
CAR_OFFSETS = [
    pygame.Vector2(-220, 160),
    pygame.Vector2(0, 220),
    pygame.Vector2(220, 160),
]

TARGET_SPAWN_INTERVAL = 2.2
MAX_TARGETS = 8

MISSILE_SPEED = 280
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
        pygame.draw.circle(surface, color, self.position, 7)
        # Draw heading indicator line
        direction = pygame.Vector2(math.cos(math.radians(self.heading)), math.sin(math.radians(self.heading)))
        end_pos = self.position + direction * 18
        pygame.draw.line(surface, color, self.position, end_pos, 2)


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
        pygame.draw.circle(surface, missile_color, self.position, 5)
        tail = self.position - self.velocity.normalize() * 12 if self.velocity.length_squared() else self.position
        pygame.draw.line(surface, missile_color, self.position, tail, 2)


@dataclass
class SupportCar:
    position: pygame.Vector2
    index: int
    cool_down: float = 0.0

    def draw(self, surface: pygame.Surface, ready: bool) -> None:
        car_color = (90, 180, 90) if ready else (70, 90, 70)
        car_rect = pygame.Rect(0, 0, 60, 36)
        car_rect.center = self.position
        pygame.draw.rect(surface, car_color, car_rect, border_radius=8)
        pygame.draw.circle(surface, (40, 40, 40), self.position + pygame.Vector2(-20, 18), 6)
        pygame.draw.circle(surface, (40, 40, 40), self.position + pygame.Vector2(20, 18), 6)


class AirDefenseGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Air Defense Simulator")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 20)
        self.big_font = pygame.font.SysFont("consolas", 32, bold=True)
        self.reset()

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

    def spawn_target(self) -> None:
        if len(self.targets) >= MAX_TARGETS:
            return
        target_type = random.choice(list(TARGET_TYPES.keys()))
        speed_range = TARGET_TYPES[target_type]["speed"]
        speed = random.uniform(*speed_range)

        angle = random.uniform(0, 360)
        spawn_distance = RADAR_RADIUS + 90
        spawn_pos = BASE_POSITION + pygame.Vector2(spawn_distance, 0).rotate(angle)

        # Determine if target aims for base or passes by
        if random.random() < 0.65:
            destination = BASE_POSITION + pygame.Vector2(random.uniform(-40, 40), random.uniform(-40, 40))
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
                if event.key in (pygame.K_1, pygame.K_2, pygame.K_3) and not self.game_over:
                    self.command_car(event.key - pygame.K_0)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not self.game_over:
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

    def command_car(self, car_index: int) -> None:
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
            if missile.target.alive and missile.position.distance_to(missile.target.position) < 12:
                missile.active = False
                missile.target.alive = False
                self.score += TARGET_TYPES[missile.target.target_type]["score"]

        # Base collision
        for target in self.targets:
            if target.position.distance_to(BASE_POSITION) < BASE_RADIUS:
                target.alive = False
                self.lives -= 1
                if self.lives <= 0:
                    self.game_over = True

        # Remove targets that escape radar bounds
        for target in self.targets:
            if target.position.distance_to(BASE_POSITION) > RADAR_RADIUS + 140:
                target.alive = False

        # Clear selection if the chosen target has been eliminated or escaped
        if self.selected_target and not self.selected_target.alive:
            self.selected_target = None

        self.targets = [target for target in self.targets if target.alive]
        self.missiles = [missile for missile in self.missiles if missile.active]

    def update(self, dt: float) -> None:
        if self.game_over:
            return
        self.elapsed += dt
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_target()
            self.spawn_timer = random.uniform(TARGET_SPAWN_INTERVAL * 0.6, TARGET_SPAWN_INTERVAL * 1.3)

        self.update_entities(dt)

    def draw_radar(self, surface: pygame.Surface, sweep_angle: float) -> None:
        pygame.draw.circle(surface, RADAR_RING_COLOR, BASE_POSITION, RADAR_RADIUS, 1)
        pygame.draw.circle(surface, RADAR_RING_COLOR, BASE_POSITION, BASE_RADIUS, 1)
        for ring in range(1, 4):
            pygame.draw.circle(surface, (30, 80, 80), BASE_POSITION, RADAR_RADIUS * ring / 4, 1)

        # Sweep line
        sweep_direction = pygame.Vector2(RADAR_RADIUS, 0).rotate(sweep_angle)
        pygame.draw.line(surface, RADAR_SWEEP_COLOR, BASE_POSITION, BASE_POSITION + sweep_direction, 2)

        # Crosshair lines
        pygame.draw.line(surface, (30, 70, 70), (BASE_POSITION.x - RADAR_RADIUS, BASE_POSITION.y), (BASE_POSITION.x + RADAR_RADIUS, BASE_POSITION.y), 1)
        pygame.draw.line(surface, (30, 70, 70), (BASE_POSITION.x, BASE_POSITION.y - RADAR_RADIUS), (BASE_POSITION.x, BASE_POSITION.y + RADAR_RADIUS), 1)

    def draw_ui(self) -> None:
        info_lines = [
            f"Score: {self.score}",
            f"Lives: {self.lives}",
            f"Targets: {len(self.targets)}",
            "Click to select target",
            "Press 1/2/3 to launch",  # instructions
        ]
        for i, line in enumerate(info_lines):
            text_surface = self.font.render(line, True, UI_TEXT_COLOR)
            self.screen.blit(text_surface, (20, 20 + i * 22))

        if self.selected_target and self.selected_target.alive:
            selected_text = self.font.render("Target locked", True, UI_TEXT_COLOR)
            self.screen.blit(selected_text, (20, 20 + len(info_lines) * 22))

        if self.game_over:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            self.screen.blit(overlay, (0, 0))
            game_over_text = self.big_font.render("Mission Failed", True, WARNING_TEXT_COLOR)
            prompt_text = self.font.render("Press R to restart", True, UI_TEXT_COLOR)
            self.screen.blit(game_over_text, game_over_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20)))
            self.screen.blit(prompt_text, prompt_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20)))

    def draw_entities(self) -> None:
        # Draw support cars
        for idx, car in enumerate(self.cars, start=1):
            ready = car.cool_down <= 0 and not self.game_over
            car.draw(self.screen, ready)
            label = self.font.render(str(idx), True, UI_TEXT_COLOR)
            self.screen.blit(label, label.get_rect(center=car.position + pygame.Vector2(0, -30)))

        # Draw base commander car
        pygame.draw.circle(self.screen, (70, 130, 160), BASE_POSITION, BASE_RADIUS)
        pygame.draw.circle(self.screen, (30, 60, 90), BASE_POSITION, BASE_RADIUS, 4)

        # Draw radar targets
        for target in self.targets:
            target.draw(self.screen)

        # Draw missiles
        for missile in self.missiles:
            missile.draw(self.screen)

        # Draw selection indicator
        if self.selected_target and self.selected_target.alive:
            pygame.draw.circle(self.screen, (255, 255, 255), self.selected_target.position, 16, 1)

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
