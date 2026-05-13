"""Skeleton of an external aim loop.

The pattern below is what an external cheat would wrap around this library:

    while running:
        target = your_detector.next_target()        # ← screen capture + ML
        if target is None:
            pad.release()
            continue
        dx = target.x - SCREEN_CENTER_X
        dy = target.y - SCREEN_CENTER_Y
        pad.move(dx, dy)

This file ships only the input half — no capture, no detector. Plug in your
own; the gamepad object only cares about dx/dy in screen pixels.
"""

import time

from game_input_bypass import VirtualGamepad

SCREEN_W, SCREEN_H = 1920, 1080
CENTER = (SCREEN_W // 2, SCREEN_H // 2)


def fake_detector():
    """Replace with a real screen-capture + detector."""
    for x in range(CENTER[0], CENTER[0] + 400, 4):
        yield (x, CENTER[1])
    while True:
        yield None


def main() -> None:
    pad = VirtualGamepad(sensitivity=0.04, max_deflection=0.75)
    try:
        for target in fake_detector():
            if target is None:
                pad.release()
                time.sleep(0.005)
                continue
            dx = target[0] - CENTER[0]
            dy = target[1] - CENTER[1]
            pad.move(dx, dy)
            time.sleep(1 / 240.0)
    finally:
        pad.release()


if __name__ == "__main__":
    main()
