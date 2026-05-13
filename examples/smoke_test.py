"""Sanity check: attach the virtual pad and sweep the right stick.

Run with the target game focused; you should see the camera pan right then
left in a sine wave. If nothing happens, verify ViGEmBus is installed
(``Get-PnpDevice -FriendlyName 'ViGEm*'``) and that the title is listed in
``game_input_bypass.detect``.
"""

import logging
import math
import time

from game_input_bypass import VirtualGamepad, detect_game

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    profile = detect_game()
    print(f"foreground profile: {profile.key if profile else 'unknown'}")

    pad = VirtualGamepad()
    try:
        for i in range(120):
            dx = math.sin(i / 10.0) * 80.0
            pad.move(dx, 0.0)
            time.sleep(1 / 120.0)
    finally:
        pad.release()


if __name__ == "__main__":
    main()
