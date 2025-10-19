# Air Defense Simulator

A lightweight radar-inspired arcade made with Pygame. Control the commander truck in the center, track approaching drones and missiles on the radar, and task one of three support launch vehicles to intercept the threats.

## Requirements

- Python 3.9+
- [Pygame](https://www.pygame.org/)

Install dependencies:

```bash
pip install pygame
```

## Running the game

```bash
python main.py
```

## How to play

1. **Detect** – Watch the radar scope for drones (blue) and missiles (red) intruding into the defensive bubble.
2. **Select** – Left click on a contact to lock it. The selected target is outlined in white.
3. **Engage** – Press `1`, `2`, or `3` to order the left, center, or right support car to launch an interceptor. Each car requires a short cool-down before firing again.
4. **Protect the command post** – If a hostile reaches the commander’s vehicle, you lose a life. Survive as long as possible and build the highest score.
5. Press `R` after defeat to restart; press `Esc` to exit.

Missiles automatically steer toward the assigned target once fired. Faster decisions lead to more successful interceptions.
