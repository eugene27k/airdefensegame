# Air Defense Simulator

A lightweight radar-inspired arcade made with Pygame. Command the central convoy from a widescreen 1440×1080 operations console, track approaching drones and missiles on the radar, and task one of three Ukrainian launch vehicles to intercept the threats.

## Requirements

- Python 3.9+
- [Pygame](https://www.pygame.org/)

Install dependencies:

```bash
pip install -r requirements.txt
```

If you encounter `ModuleNotFoundError: No module named 'pygame'`, ensure the command above
was executed in the same virtual environment you use to launch the game.

## Running the game

```bash
python main.py
```

## How to play

1. **Detect** – Watch the expanded radar scope for drones (blue) and missiles (red) intruding into the defensive bubble.
2. **Select** – Left click on a contact to lock it. A pulsing reticle highlights the chosen target and turrets on each vehicle swivel toward the threat.
3. **Engage** – Press `1`, `2`, or `3` to order the left, northern, or right support car to launch an interceptor. Each car requires a short cool-down before firing again.
4. **Advance levels** – Destroy 20 targets to complete the current mission. Every new level raises hostile speeds by 10 % and doubles the points earned per kill. A speed readout in the lower-right corner confirms each contact’s current velocity and the average pace per wave.
5. **Protect the command post** – If a hostile reaches the commander’s vehicle, you lose a life. Press `R` after defeat to restart; press `Esc` to exit.

Each support vehicle proudly carries a Ukrainian flag, and an opening splash screen sets the tone before hostilities begin.

Missiles automatically steer toward the assigned target once fired. Faster decisions lead to more successful interceptions.
