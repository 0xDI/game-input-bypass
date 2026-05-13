"""Minimal sanity check.

Resolves the active channel for the foreground window, prints it, then sends
a few small movements. Run this with Notepad focused to verify mouse_event,
or with Fortnite focused to verify the ViGEm pad attaches.
"""

import logging
import time

from game_input_bypass import InputBypass, detect_game

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    profile = detect_game()
    print(f"foreground profile: {profile.key if profile else 'unknown'}")

    ib = InputBypass()
    for _ in range(20):
        ib.move(5, 0)
        time.sleep(0.02)
    ib.release()


if __name__ == "__main__":
    main()
