"""Concrete input channels.

Two implementations of the `Channel` protocol:

    VirtualGamepad      XInput 360 pad emulated through the ViGEmBus driver.
    MouseEventInjector  user32!mouse_event (legacy, no driver required).
"""

from __future__ import annotations

import math
import time
from typing import Protocol

import win32api
import win32con


class Channel(Protocol):
    def move(self, dx: float, dy: float) -> None: ...
    def click(self, hold_ms: int = 10) -> None: ...
    def release(self) -> None: ...


# ────────────────────────────── gamepad ──────────────────────────────────

class VirtualGamepad:
    """XInput 360 controller backed by ViGEmBus.

    Movement is delivered as a right-stick deflection. Pixel-space error is
    mapped to the unit square through `sensitivity` and clamped to
    `max_deflection` so the stick never pegs (engines treat a pegged stick as
    a snap and apply a smoothing curve we cannot predict).

    Requires:
        ViGEmBus driver  https://github.com/nefarius/ViGEmBus
        vgamepad         pip install vgamepad
    """

    def __init__(self,
                 sensitivity: float = 0.035,
                 max_deflection: float = 0.80,
                 dead_zone_px: float = 3.0) -> None:
        import vgamepad as vg
        self._vg = vg
        self._pad = vg.VX360Gamepad()
        self.sensitivity = sensitivity
        self.max_deflection = max_deflection
        self.dead_zone_px = dead_zone_px
        self._prime()

    def _prime(self) -> None:
        # Force the game into controller mode by emitting a non-zero deflection
        # on attach. Some titles only switch input maps after the first packet.
        self._pad.right_joystick_float(x_value_float=0.1, y_value_float=0.0)
        self._pad.update()
        time.sleep(0.1)
        self.release()

    def move(self, dx: float, dy: float) -> None:
        if math.hypot(dx, dy) < self.dead_zone_px:
            self.release()
            return
        c = self.max_deflection
        sx = max(-c, min(c, dx * self.sensitivity))
        sy = max(-c, min(c, -dy * self.sensitivity))   # screen Y is inverted
        self._pad.right_joystick_float(x_value_float=sx, y_value_float=sy)
        self._pad.update()

    def release(self) -> None:
        self._pad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
        self._pad.update()

    def click(self, hold_ms: int = 10) -> None:
        self._pad.right_trigger_float(value_float=1.0)
        self._pad.update()
        time.sleep(hold_ms / 1000.0)
        self._pad.right_trigger_float(value_float=0.0)
        self._pad.update()


# ────────────────────────────── mouse_event ──────────────────────────────

class MouseEventInjector:
    """user32!mouse_event — the original Win9x mouse path.

    Most pre-Source2 era titles still consume these events without filtering,
    which makes this the most compatible channel for CS:GO/CS2/TF2/L4D2.
    """

    def move(self, dx: float, dy: float) -> None:
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)

    def click(self, hold_ms: int = 10) -> None:
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(hold_ms / 1000.0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def release(self) -> None:   # stateless
        return
