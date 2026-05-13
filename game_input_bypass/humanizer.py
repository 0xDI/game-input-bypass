"""Behavioral shaping layer for :class:`VirtualGamepad`.

Raw stick output from a detector loop has a number of signatures that make
it trivial to flag as machine-generated:

* Step response is instantaneous (no acceleration phase).
* Output is bit-exact when given the same input twice.
* No physiological tremor — the stick rests at a perfect zero.
* No reaction-time gap between target appearance and aim onset.
* Snap-aim has no overshoot/correct phase.

``HumanizedGamepad`` wraps a :class:`VirtualGamepad` and shapes its output
so each of those signatures is replaced by a plausible human one. It is a
drop-in replacement for ``VirtualGamepad`` from the consumer's perspective:

    pad = HumanizedGamepad()
    while running:
        pad.move(dx, dy)         # same signature, same units (pixels)

The shaping happens entirely in stick space, so it is independent of the
target game and of the detector that produced ``(dx, dy)``.

Components
----------

1. **Reaction delay.** When the input changes by more than
   ``reaction_trigger_px`` (a new target acquired), the output stick is
   *held* for a uniformly distributed delay in the
   ``[reaction_ms_min, reaction_ms_max]`` band — corresponding to human
   choice-reaction time (~80-150 ms).

2. **Exponential easing.** The stick approaches the desired deflection
   through a first-order low-pass filter with time constant
   ``easing_tau_ms``. Frame-rate independent: identical motion at any
   loop frequency.

3. **Physiological tremor.** A 2-D Ornstein-Uhlenbeck process driven at
   ``tremor_band_hz`` (~8 Hz peak, matching the 6-12 Hz physiologic
   action-tremor band) and ``tremor_amplitude`` (stick units) is added to
   the output every frame. OU is the standard model for low-pass
   biological noise; output is smooth, mean-reverting and never repeats.

4. **Overshoot + correction.** On snaps larger than
   ``overshoot_trigger_px``, the desired deflection is briefly amplified
   by ``overshoot_factor`` (~5-10 %) before settling, producing the
   characteristic over-and-back signature of a fast saccade.

5. **Idle drift.** When no target is being tracked, the stick decays
   toward zero through the same filter but the tremor keeps emitting, so
   the controller never reads as "dead" between targets.

All five layers run regardless of which one currently dominates output;
they are not modes. The result is one stream of ``set_stick()`` calls per
frame.
"""

from __future__ import annotations

import math
import random
import time
from typing import Callable, Optional

from .gamepad import VirtualGamepad

Clock = Callable[[], float]


class HumanizedGamepad:
    """Drop-in replacement for :class:`VirtualGamepad` with behavioral shaping.

    Parameters
    ----------
    pad:
        Existing :class:`VirtualGamepad`. One is constructed with defaults
        if omitted.

    sensitivity, max_deflection:
        Same meaning as on :class:`VirtualGamepad`. Re-declared here because
        we bypass the underlying pad's mapping.

    reaction_ms_min, reaction_ms_max, reaction_trigger_px:
        Reaction-delay band, and the input-jump threshold (in pixels) that
        triggers it.

    easing_tau_ms:
        Time constant of the first-order low-pass approach. ~80 ms feels
        snappy without being instant.

    tremor_amplitude, tremor_band_hz:
        Ornstein-Uhlenbeck tremor params. Stationary std equals
        ``tremor_amplitude`` (stick units). ``tremor_band_hz`` controls the
        spectral roll-off.

    overshoot_factor, overshoot_ms, overshoot_trigger_px:
        Brief amplification window applied immediately after reaction delay
        on large snaps.

    idle_drift:
        When True, the tremor source keeps writing during ``release()`` so
        idle frames don't read as a frozen stick.

    seed:
        Seed for the noise RNG. Leave None for non-deterministic output.
    """

    def __init__(
        self,
        pad: Optional[VirtualGamepad] = None,
        *,
        sensitivity: float = 0.035,
        max_deflection: float = 0.80,
        reaction_ms_min: float = 80.0,
        reaction_ms_max: float = 150.0,
        reaction_trigger_px: float = 60.0,
        easing_tau_ms: float = 80.0,
        tremor_amplitude: float = 0.006,
        tremor_band_hz: float = 8.0,
        overshoot_factor: float = 1.08,
        overshoot_ms: float = 35.0,
        overshoot_trigger_px: float = 120.0,
        idle_drift: bool = True,
        seed: Optional[int] = None,
        clock: Clock = time.perf_counter,
    ) -> None:
        # The wrapped pad bypasses its own dead-zone (we manage that here).
        self.pad = pad or VirtualGamepad(sensitivity=sensitivity,
                                         max_deflection=max_deflection,
                                         dead_zone_px=0.0)

        self.sensitivity = sensitivity
        self.max_deflection = max_deflection

        self.reaction_ms_min = reaction_ms_min
        self.reaction_ms_max = reaction_ms_max
        self.reaction_trigger_px = reaction_trigger_px

        self._tau = easing_tau_ms / 1000.0

        # OU parameters. For stationary std == amplitude:
        #     sigma = amplitude * sqrt(2 * theta)
        self._tremor_theta = 2.0 * math.pi * tremor_band_hz
        self._tremor_sigma = tremor_amplitude * math.sqrt(2.0 * self._tremor_theta)

        self.overshoot_factor = overshoot_factor
        self._overshoot_dur = overshoot_ms / 1000.0
        self.overshoot_trigger_px = overshoot_trigger_px

        self.idle_drift = idle_drift
        self._rng = random.Random(seed)
        self._clock = clock

        # Persistent state.
        self._stick_x = 0.0
        self._stick_y = 0.0
        self._tremor_x = 0.0
        self._tremor_y = 0.0
        self._last_t: Optional[float] = None
        self._last_dx = 0.0
        self._last_dy = 0.0
        self._reaction_until = 0.0
        self._overshoot_until = 0.0

    # ───────────────────────────── internals ──────────────────────────────
    def _step_tremor(self, dt: float) -> None:
        """Advance the Ornstein-Uhlenbeck tremor by `dt` seconds."""
        # dx = -theta * x * dt + sigma * sqrt(dt) * N(0, 1)
        sqrt_dt = math.sqrt(max(dt, 1e-9))
        kx = -self._tremor_theta * self._tremor_x * dt
        ky = -self._tremor_theta * self._tremor_y * dt
        nx = self._rng.gauss(0.0, 1.0)
        ny = self._rng.gauss(0.0, 1.0)
        self._tremor_x += kx + self._tremor_sigma * sqrt_dt * nx
        self._tremor_y += ky + self._tremor_sigma * sqrt_dt * ny

    def _tick(self) -> float:
        """Return dt since the last call; initialise on first use."""
        now = self._clock()
        if self._last_t is None:
            self._last_t = now
            return 1.0 / 60.0
        dt = max(1e-4, now - self._last_t)
        self._last_t = now
        return dt

    @staticmethod
    def _clamp(v: float, lo: float, hi: float) -> float:
        return lo if v < lo else hi if v > hi else v

    def _emit(self, sx: float, sy: float) -> None:
        self.pad.set_stick(self._clamp(sx, -1.0, 1.0),
                           self._clamp(sy, -1.0, 1.0))

    # ─────────────────────────────── public ───────────────────────────────
    def move(self, dx: float, dy: float) -> None:
        """Shape and emit one frame of stick output toward pixel error (dx, dy)."""
        now_dt = self._tick()
        now = self._last_t  # type: ignore[assignment]

        # Detect a "new target" event via a large change in input vector.
        jump = math.hypot(dx - self._last_dx, dy - self._last_dy)
        if jump > self.reaction_trigger_px:
            self._reaction_until = now + self._rng.uniform(
                self.reaction_ms_min, self.reaction_ms_max) / 1000.0
            if jump > self.overshoot_trigger_px:
                self._overshoot_until = self._reaction_until + self._overshoot_dur
        self._last_dx, self._last_dy = dx, dy

        self._step_tremor(now_dt)

        # During reaction delay we hold the current stick + tremor.
        if now < self._reaction_until:
            self._emit(self._stick_x + self._tremor_x,
                       self._stick_y + self._tremor_y)
            return

        # Map pixel error to stick deflection.
        c = self.max_deflection
        desired_x = self._clamp(dx * self.sensitivity, -c, c)
        desired_y = self._clamp(-dy * self.sensitivity, -c, c)  # screen Y inverted

        # Brief overshoot after a snap.
        if now < self._overshoot_until:
            desired_x *= self.overshoot_factor
            desired_y *= self.overshoot_factor

        # First-order low-pass approach: alpha = 1 - exp(-dt / tau).
        alpha = 1.0 - math.exp(-now_dt / self._tau)
        self._stick_x += (desired_x - self._stick_x) * alpha
        self._stick_y += (desired_y - self._stick_y) * alpha

        self._emit(self._stick_x + self._tremor_x,
                   self._stick_y + self._tremor_y)

    def release(self) -> None:
        """Decay toward neutral; tremor keeps emitting if idle_drift is on."""
        now_dt = self._tick()
        self._step_tremor(now_dt)

        alpha = 1.0 - math.exp(-now_dt / self._tau)
        self._stick_x += (0.0 - self._stick_x) * alpha
        self._stick_y += (0.0 - self._stick_y) * alpha

        if self.idle_drift:
            self._emit(self._stick_x + self._tremor_x,
                       self._stick_y + self._tremor_y)
        else:
            self._emit(self._stick_x, self._stick_y)

        # Reset jump tracking so the next acquired target re-triggers reaction.
        self._last_dx = 0.0
        self._last_dy = 0.0

    def click(self, hold_ms: int = 10) -> None:
        """Trigger pull with naturalistic hold-time jitter (4-15 ms band)."""
        jitter = self._rng.uniform(-3.0, 5.0)
        self.pad.click(max(4, int(hold_ms + jitter)))

    def left_trigger(self, value: float) -> None:
        self.pad.left_trigger(value)
