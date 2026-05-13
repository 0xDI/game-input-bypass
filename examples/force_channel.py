"""Force a specific channel regardless of foreground window.

    python examples/force_channel.py gamepad
    python examples/force_channel.py mouse_event
"""

import sys
import time

from game_input_bypass import InputBypass


def main(channel: str) -> None:
    ib = InputBypass(channel=channel)
    for i in range(30):
        ib.move(8 if i % 2 == 0 else -8, 0)
        time.sleep(0.03)
    ib.release()


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("gamepad", "mouse_event"):
        sys.exit("usage: force_channel.py {gamepad|mouse_event}")
    main(sys.argv[1])
