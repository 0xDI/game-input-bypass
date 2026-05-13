"""ViGEmBus-backed XInput 360 controller."""

from __future__ import annotations

import logging
import math
import time

log = logging.getLogger(__name__)


class VirtualGamepad:
    """XInput 360 controller emulated through the ViGEmBus kernel driver.

    The driver is Microsoft-signed; the device it exposes is indistinguishable
    from a real Xbox controller from user-mode. Games read it through the
    XInput API and receive HID reports that carry none of the synthetic-input
    flags (`LLMHF_INJECTED` and friends) that mark `SendInput`-originated events.

    Movement model
    --------------
    The right stick is driven as a velocity vector toward the on-screen target.
    Pixel-space error (dx, dy) is mapped to the unit square through
    `sensitivity` and clamped to `max_deflection`. A small dead zone suppresses
    micro-deflections that would otherwise produce visible judder in-engine.

    Requires
    --------
    * ViGEmBus driver  https://github.com/nefarius/ViGEmBus
    * vgamepad         ``pip install vgamepad``
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
        log.info("ViGEm gamepad attached (sensitivity=%.3f, max=%.2f)",
                 sensitivity, max_deflection)

    # ── internal ──────────────────────────────────────────────────────────
    def _prime(self) -> None:
        # Emit one non-zero deflection on attach. Some titles only switch
        # their active input map after seeing the first packet.
        self._pad.right_joystick_float(x_value_float=0.1, y_value_float=0.0)
        self._pad.update()
        time.sleep(0.1)
        self.release()

    # ── public API ────────────────────────────────────────────────────────
    def move(self, dx: float, dy: float) -> None:
        """Aim toward an offset of (dx, dy) pixels from the crosshair."""
        if math.hypot(dx, dy) < self.dead_zone_px:
            self.release()
            return
        c = self.max_deflection
        sx = max(-c, min(c, dx * self.sensitivity))
        sy = max(-c, min(c, -dy * self.sensitivity))   # screen Y is inverted
        self._pad.right_joystick_float(x_value_float=sx, y_value_float=sy)
        self._pad.update()

    def release(self) -> None:
        """Return the stick to neutral."""
        self._pad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
        self._pad.update()

    def set_stick(self, sx: float, sy: float) -> None:
        """Set right-stick deflection directly in normalized [-1, 1] units.

        Bypasses sensitivity / dead-zone / clamping. Used by higher-level
        shaping layers (see :class:`HumanizedGamepad`) that compute their own
        deflection in stick space.
        """
        sx = max(-1.0, min(1.0, sx))
        sy = max(-1.0, min(1.0, sy))
        self._pad.right_joystick_float(x_value_float=sx, y_value_float=sy)
        self._pad.update()

    def click(self, hold_ms: int = 10) -> None:
        """Pull the right trigger (primary fire on a controller)."""
        self._pad.right_trigger_float(value_float=1.0)
        self._pad.update()
        time.sleep(hold_ms / 1000.0)
        self._pad.right_trigger_float(value_float=0.0)
        self._pad.update()

    def left_trigger(self, value: float) -> None:
        """Set left-trigger pull (0.0 - 1.0). Common ADS binding."""
        self._pad.left_trigger_float(value_float=max(0.0, min(1.0, value)))
        self._pad.update()
