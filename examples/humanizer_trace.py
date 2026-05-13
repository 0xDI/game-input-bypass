"""Deterministic, headless trace of HumanizedGamepad output.

The pad and the clock are both mocked, so no ViGEmBus driver is required
and the run is bit-reproducible across machines. The output lets you
verify the four visible signatures of human-like aim:

  1. Idle phase before any target  →  near-zero mean, small tremor std
  2. Snap onset                    →  reaction-hold then rapid pull
  3. Steady tracking               →  stick near max_deflection, with tremor
  4. Release                       →  exponential decay back to zero

Run:
    python examples/humanizer_trace.py
"""

from __future__ import annotations

import statistics
from typing import List, Tuple

from game_input_bypass.humanizer import HumanizedGamepad


FRAME_HZ = 240
FRAME_DT = 1.0 / FRAME_HZ


# ─────────────────────────── Mocks ───────────────────────────

class _MockPad:
    """Stand-in for VirtualGamepad that records every stick write."""
    def __init__(self) -> None:
        self.samples: List[Tuple[float, float]] = []

    def set_stick(self, sx: float, sy: float) -> None:
        self.samples.append((sx, sy))

    def click(self, hold_ms: int = 10) -> None:
        pass

    def left_trigger(self, value: float) -> None:
        pass


class _VirtualClock:
    """Monotonic counter that advances by FRAME_DT per tick()."""
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def tick(self) -> None:
        self.t += FRAME_DT


# ─────────────────────────── Helpers ──────────────────────────

def _summarise(label: str, samples: List[Tuple[float, float]]) -> None:
    xs = [s[0] for s in samples]
    print(f"  {label:<22}"
          f" n={len(xs):4d}"
          f"  mean={statistics.fmean(xs):+.4f}"
          f"  std={statistics.pstdev(xs):.4f}"
          f"  min={min(xs):+.4f}"
          f"  max={max(xs):+.4f}")


def _run(human: HumanizedGamepad, clock: _VirtualClock,
         action: str, frames: int, dx: float = 0.0) -> int:
    pre = len(human.pad.samples)        # type: ignore[union-attr]
    for _ in range(frames):
        if action == "move":
            human.move(dx, 0.0)
        else:
            human.release()
        clock.tick()
    return pre


# ─────────────────────────── Main ─────────────────────────────

def main() -> None:
    clock = _VirtualClock()
    human = HumanizedGamepad(pad=_MockPad(),       # type: ignore[arg-type]
                             seed=42,
                             clock=clock)
    pad: _MockPad = human.pad                       # type: ignore[assignment]

    print(f"clock: virtual @ {FRAME_HZ} Hz   seed: 42\n")

    # 1. Idle baseline (1 s)
    pre = _run(human, clock, "release", FRAME_HZ)
    _summarise("idle baseline", pad.samples[pre:])

    # 2. Snap onset — 30 frames after target appears
    pre = _run(human, clock, "move", 30, dx=200.0)
    _summarise("snap (reaction + pull)", pad.samples[pre:])

    # 3. Steady tracking (1 s)
    pre = _run(human, clock, "move", FRAME_HZ, dx=200.0)
    _summarise("steady tracking", pad.samples[pre:])

    # 4. Release decay (1 s)
    pre = _run(human, clock, "release", FRAME_HZ)
    _summarise("release decay", pad.samples[pre:])

    print(f"\ntotal samples emitted: {len(pad.samples)}")

    # Quick assertions — fail loudly if the curve regresses.
    idle = pad.samples[:FRAME_HZ]
    idle_x = [s[0] for s in idle]
    idle_std = statistics.pstdev(idle_x)
    assert idle_std > 1e-4, f"tremor too small: std={idle_std}"
    assert abs(statistics.fmean(idle_x)) < 0.005, "idle should mean-revert"

    track = pad.samples[FRAME_HZ + 30 : 2 * FRAME_HZ + 30]
    track_mean = statistics.fmean(s[0] for s in track)
    assert track_mean > 0.5, f"steady tracking should approach max_deflection (got {track_mean})"

    decay_end = pad.samples[-FRAME_HZ // 4:]   # last 0.25 s of release
    decay_mean = abs(statistics.fmean(s[0] for s in decay_end))
    assert decay_mean < 0.05, f"stick did not decay (got {decay_mean})"

    print("checks passed: tremor present, tracking settles, release decays")


if __name__ == "__main__":
    main()
