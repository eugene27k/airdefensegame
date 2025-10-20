
try:
    from importlib.util import find_spec as _find_spec
except ImportError:  # pragma: no cover - legacy Python fallback
    from importlib import find_loader as _find_spec  # type: ignore[attr-defined]
import math
import random
import sys
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

# created by Eugene K - the BA

if _find_spec("pygame") is None:
    sys.stderr.write(
        "Pygame is required to run Air Defense Simulator.\n"
        "Install dependencies with 'pip install -r requirements.txt' and try again.\n"
    )
    sys.exit(1)

import pygame

pygame.mixer.pre_init(22050, 8, 1, 256)

# Global scale to boost resolution while keeping aspect ratio
SCALE = 1.5
SAMPLE_RATE = 22050

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


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def lerp_color(color_a: Tuple[int, int, int], color_b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(a + (b - a) * t) for a, b in zip(color_a, color_b))


def build_tone_buffer(sequence: Sequence[Tuple[float, float, float, bool]]) -> bytes:
    buffer = bytearray()
    for frequency, duration, volume, decay in sequence:
        total_samples = max(1, int(SAMPLE_RATE * duration))
        amplitude = int(127 * clamp(volume, 0.0, 1.0))
        if frequency <= 0:
            buffer.extend([128] * total_samples)
            continue
        period = max(1, int(SAMPLE_RATE / frequency))
        half_period = max(1, period // 2)
        for i in range(total_samples):
            if decay:
                current_amplitude = int(amplitude * (1 - i / total_samples))
            else:
                current_amplitude = amplitude
            toggle = 1 if ((i // half_period) % 2 == 0) else -1
            sample_value = 128 + toggle * current_amplitude
            buffer.append(int(clamp(sample_value, 0, 255)))
    return bytes(buffer)


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
class Explosion:
    position: pygame.Vector2
    timer: float = 0.0
    lifetime: float = 0.6

    def update(self, dt: float) -> None:
        self.timer += dt

    @property
    def alive(self) -> bool:
        return self.timer < self.lifetime

    def draw(self, surface: pygame.Surface) -> None:
        progress = min(1.0, self.timer / self.lifetime)
        min_radius = 14 * SCALE
        max_radius = 54 * SCALE
        radius = max(1, int(min_radius + (max_radius - min_radius) * progress))
        size = radius * 2
        explosion_surface = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (radius, radius)

        outer_alpha = max(0, int(200 * (1 - progress)))
        inner_alpha = max(0, int(255 * (1 - progress * 0.8)))

        pygame.draw.circle(explosion_surface, (255, 140, 60, outer_alpha), center, radius)
        pygame.draw.circle(
            explosion_surface,
            (255, 230, 180, inner_alpha),
            center,
            max(1, int(radius * 0.6)),
        )

        surface.blit(explosion_surface, explosion_surface.get_rect(center=self.position))


@dataclass
class SupportCar:
    position: pygame.Vector2
    index: int
    cool_down: float = 0.0

    def draw(
        self,
        surface: pygame.Surface,
        ready: bool,
        selected_target: Optional[Target],
        font: pygame.font.Font,
    ) -> None:
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

        label_color = (20, 40, 20) if ready else (110, 110, 110)
        label_surface = font.render(str(self.index), True, label_color)
        label_rect = label_surface.get_rect(center=self.position)
        surface.blit(label_surface, label_rect)

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
        pygame.display.set_caption("Air Defense Simulator – Made by Eugene K - the BA")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", int(20 * SCALE))
        self.big_font = pygame.font.SysFont("consolas", int(32 * SCALE), bold=True)
        self.title_font = pygame.font.SysFont("consolas", int(48 * SCALE), bold=True)
        self.subtitle_font = pygame.font.SysFont("consolas", int(28 * SCALE))
        self.audio_enabled = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.setup_audio()
        self.has_started = False
        self.reset()
        self.show_intro()

    def reset(self) -> None:
        self.targets: List[Target] = []
        self.missiles: List[Missile] = []
        self.explosions: List[Explosion] = []
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
        self.radar_damage_timer = 0.0
        self.apply_level_parameters()
        if self.has_started:
            self.play_sound("start")
        else:
            self.has_started = True

    def apply_level_parameters(self) -> None:
        self.enemy_speed_multiplier = 1.0 + 0.05 * (self.level - 1)
        self.score_multiplier = 2 ** (self.level - 1)

    def setup_audio(self) -> None:
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(22050, 8, 1, 256)
        except pygame.error:
            self.audio_enabled = False
            self.sounds = {}
            return
        self.audio_enabled = True
        self.load_sounds()

    def load_sounds(self) -> None:
        if not self.audio_enabled:
            return

        def make_sound(sequence: Sequence[Tuple[float, float, float, bool]]) -> pygame.mixer.Sound:
            return pygame.mixer.Sound(buffer=build_tone_buffer(sequence))
        try:
            self.sounds = {
                "shot": make_sound(((1200, 0.12, 0.7, True),)),
                "explosion": make_sound(((220, 0.24, 0.85, True), (90, 0.34, 0.75, True))),
                "damage": make_sound(((200, 0.16, 0.8, False), (70, 0.24, 0.85, True))),
                "start": make_sound(((360, 0.12, 0.6, False), (540, 0.12, 0.6, False), (720, 0.18, 0.5, True))),
                "game_over": make_sound(((260, 0.28, 0.75, True), (150, 0.32, 0.7, True))),
            }
        except pygame.error:
            self.audio_enabled = False
            self.sounds = {}

    def play_sound(self, key: str) -> None:
        if not self.audio_enabled:
            return
        sound = self.sounds.get(key)
        if sound:
            sound.play()

    def start_level_complete(self) -> None:
        self.level_complete = True
        self.level_transition_timer = LEVEL_COMPLETE_PAUSE
        self.selected_target = None
        self.lock_timer = 0.0
        for target in self.targets:
            target.alive = False
        for missile in self.missiles:
            missile.active = False
        self.explosions.clear()

    def advance_level(self) -> None:
        self.level += 1
        self.level_complete = False
        self.level_transition_timer = 0.0
        self.targets_destroyed = 0
        self.apply_level_parameters()
        self.spawn_timer = TARGET_SPAWN_INTERVAL
        self.targets.clear()
        self.missiles.clear()
        self.explosions.clear()
        self.selected_target = None
        self.lock_timer = 0.0

    def show_intro(self) -> None:
        intro_duration = 2.5
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
        self.play_sound("start")

    def spawn_target(self) -> None:
        if len(self.targets) >= MAX_TARGETS:
            return
        target_type = random.choice(list(TARGET_TYPES.keys()))
        speed_range = TARGET_TYPES[target_type]["speed"]
        base_speed = random.uniform(*speed_range) * 0.8
        speed = base_speed * self.enemy_speed_multiplier

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
        self.play_sound("shot")

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
                self.explosions.append(Explosion(missile.target.position.copy()))
                self.play_sound("explosion")
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
                self.radar_damage_timer = 0.5
                self.play_sound("damage")
                if self.lives <= 0 and not self.game_over:
                    self.game_over = True
                    self.play_sound("game_over")

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
        self.radar_damage_timer = max(0.0, self.radar_damage_timer - dt)
        for explosion in self.explosions:
            explosion.update(dt)
        self.explosions = [explosion for explosion in self.explosions if explosion.alive]

        if self.game_over:
            self.lock_timer = 0.0
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

    def draw_radar(self, surface: pygame.Surface, sweep_angle: float, damage_flash: float) -> None:
        ring_width = max(1, int(2 * SCALE))
        radar_background_color = lerp_color((12, 22, 32), (150, 40, 40), damage_flash)
        ring_color = lerp_color(RADAR_RING_COLOR, (220, 70, 70), damage_flash)
        sweep_color = lerp_color(RADAR_SWEEP_COLOR, (255, 90, 90), damage_flash)
        crosshair_color = lerp_color((30, 70, 70), (190, 60, 60), damage_flash)

        pygame.draw.circle(surface, radar_background_color, BASE_POSITION, RADAR_RADIUS)
        pygame.draw.circle(surface, ring_color, BASE_POSITION, RADAR_RADIUS, ring_width)
        pygame.draw.circle(surface, ring_color, BASE_POSITION, BASE_RADIUS, max(1, int(1 * SCALE)))
        for ring in range(1, 4):
            pygame.draw.circle(
                surface,
                lerp_color((30, 80, 80), (200, 90, 90), damage_flash),
                BASE_POSITION,
                RADAR_RADIUS * ring / 4,
                max(1, int(SCALE)),
            )

        # Sweep line
        sweep_direction = pygame.Vector2(RADAR_RADIUS, 0).rotate(sweep_angle)
        pygame.draw.line(surface, sweep_color, BASE_POSITION, BASE_POSITION + sweep_direction, max(1, int(2 * SCALE)))

        # Crosshair lines
        crosshair_width = max(1, int(SCALE))
        pygame.draw.line(
            surface,
            crosshair_color,
            (BASE_POSITION.x - RADAR_RADIUS, BASE_POSITION.y),
            (BASE_POSITION.x + RADAR_RADIUS, BASE_POSITION.y),
            crosshair_width,
        )
        pygame.draw.line(
            surface,
            crosshair_color,
            (BASE_POSITION.x, BASE_POSITION.y - RADAR_RADIUS),
            (BASE_POSITION.x, BASE_POSITION.y + RADAR_RADIUS),
            crosshair_width,
        )

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
            game_over_text = self.big_font.render("Game Over", True, WARNING_TEXT_COLOR)
            score_text = self.font.render(f"Final Score: {self.score}", True, UI_TEXT_COLOR)
            prompt_text = self.font.render("Press R to restart", True, UI_TEXT_COLOR)
            center_y = SCREEN_HEIGHT // 2
            self.screen.blit(game_over_text, game_over_text.get_rect(center=(SCREEN_WIDTH // 2, center_y - 30 * SCALE)))
            self.screen.blit(score_text, score_text.get_rect(center=(SCREEN_WIDTH // 2, center_y)))
            self.screen.blit(prompt_text, prompt_text.get_rect(center=(SCREEN_WIDTH // 2, center_y + 30 * SCALE)))
        elif self.level_complete:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 30, 0, 140))
            self.screen.blit(overlay, (0, 0))
            complete_text = self.big_font.render("Mission Complete", True, SUCCESS_TEXT_COLOR)
            next_level_text = self.font.render(f"Level {self.level + 1} incoming", True, UI_TEXT_COLOR)
            self.screen.blit(complete_text, complete_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20 * SCALE)))
            self.screen.blit(next_level_text, next_level_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20 * SCALE)))

    def draw_entities(self, damage_flash: float) -> None:
        # Draw support cars
        active_target = self.selected_target if self.selected_target and self.selected_target.alive else None
        for car in self.cars:
            ready = car.cool_down <= 0 and not self.game_over
            car.draw(self.screen, ready, active_target, self.font)

        # Draw base commander car
        base_color = lerp_color((70, 130, 160), (220, 70, 70), damage_flash)
        base_outline = lerp_color((30, 60, 90), (180, 40, 40), damage_flash)
        pygame.draw.circle(self.screen, base_color, BASE_POSITION, BASE_RADIUS)
        pygame.draw.circle(self.screen, base_outline, BASE_POSITION, BASE_RADIUS, max(2, int(4 * SCALE)))

        # Draw radar targets
        for target in self.targets:
            target.draw(self.screen)

        # Draw missiles
        for missile in self.missiles:
            missile.draw(self.screen)

        # Draw explosions
        for explosion in self.explosions:
            explosion.draw(self.screen)

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
        damage_flash = self.radar_damage_timer / 0.5 if self.radar_damage_timer > 0 else 0.0
        self.draw_radar(self.screen, sweep_angle, damage_flash)
        self.draw_entities(damage_flash)
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
