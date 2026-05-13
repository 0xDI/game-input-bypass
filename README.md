<h1 align="center">game-input-bypass</h1>

<p align="center">
  <strong>An external, fully user-mode input layer for Win32 games that filter synthetic input.</strong>
  <br/>
  Two stacked defenses:
  a Microsoft-signed virtual HID controller to defeat <em>injection</em> detection,
  and a physiologically-modelled stick humanizer to defeat <em>behavioral</em> detection.
</p>

<p align="center">
  <a href="#"><img alt="python"     src="https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white"></a>
  <a href="#"><img alt="platform"   src="https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white"></a>
  <a href="#"><img alt="license"    src="https://img.shields.io/badge/license-MIT-green"></a>
  <a href="#"><img alt="status"     src="https://img.shields.io/badge/status-undetected%20%E2%80%94%20May%202026-success"></a>
  <a href="#"><img alt="invasive"   src="https://img.shields.io/badge/process%20touched-none-informational"></a>
  <a href="#"><img alt="signal"     src="https://img.shields.io/badge/output-humanized-9cf"></a>
</p>

---

## TL;DR

- **External.** The cheat process never touches the game's memory or modules.
  No DLL injection, no API hooks, no `OpenProcess`, no kernel driver of our own.
- **Two-layer bypass.**
  Synthetic input flags (`LLMHF_INJECTED`) and synthetic-source filtering are
  defeated by routing through a signed virtual HID device.
  Stick-curve heuristics are defeated by an Ornstein-Uhlenbeck tremor model
  with reaction-delay gating and overshoot.
- **Undetected as of May 2026** on every title in the supported list.
  ViGEmBus is Microsoft-signed and ships in Steam Input, DS4Windows, reWASD
  and the Xbox Accessories app, so removing it is not on the table.

---

## Contents

- [The two defenses it bypasses](#the-two-defenses-it-bypasses)
- [What "external" means](#what-external-means)
- [Install](#install)
- [Quick start](#quick-start)
- [`HumanizedGamepad` — behavioral shaping](#humanizedgamepad--behavioral-shaping)
- [`VirtualGamepad` — the injection bypass](#virtualgamepad--the-injection-bypass)
- [What is blocked, and why we don't use it](#what-is-blocked-and-why-we-dont-use-it)
- [How it works end-to-end](#how-it-works-end-to-end)
- [Supported games](#supported-games)
- [Project layout](#project-layout)
- [FAQ](#faq)
- [Disclaimer](#disclaimer)

---

## The two defenses it bypasses

Modern PC games protect themselves against external automation along two
orthogonal axes. A library that only addresses one of them stops working as
soon as the other fires.

### 1. Injection detection — "did this input come from software?"

Every event sent through `SendInput` / `keybd_event` carries a kernel-set
`LLMHF_INJECTED` flag visible to low-level hooks. UE5 and modern Source-2
based engines additionally check whether the event's
`RAWINPUTHEADER.hDevice` resolves to a registered HID mouse, and apply a
non-removable smoothing curve to anything that doesn't.

**Defeated by:** `VirtualGamepad`, which routes input through the
Microsoft-signed **ViGEmBus** driver. ViGEmBus exposes a real HID controller
device to the kernel. The XInput packets it emits carry no injection flag
because there is no injection — to the OS, an Xbox controller is plugged in.

### 2. Behavioral detection — "does this input look human?"

Even if the event-source check passes, the *stick signal* itself is
informative. Raw automated output has telltale signatures: instantaneous
step response, bit-exact repeatability, perfect zero at rest, zero reaction
delay between target acquisition and aim onset, no overshoot phase on snaps.
Vanguard, Ricochet, EA Javelin, and FaceIt's curve analysis all look at
these.

**Defeated by:** `HumanizedGamepad`, which wraps `VirtualGamepad` and
replaces each signature with a physiologically plausible substitute:
reaction-delay gating, exponential easing, an Ornstein-Uhlenbeck tremor
process tuned to the 6-12 Hz action-tremor band, brief overshoot-and-correct
on large snaps, and idle drift so the controller never reads as a frozen
stick.

---

## What "external" means

Spelled out, because the word is overused:

- No `OpenProcess`, `ReadProcessMemory`, `WriteProcessMemory`.
- No DLL injection, no `CreateRemoteThread`, no manual mapping.
- No `SetWindowsHookEx` against the game's threads.
- No driver of our own. ViGEmBus is a third-party Microsoft-signed driver
  installed system-wide by the user, identical to the one Steam Input
  installs.

The cheat process runs in its own address space, captures the screen with
the standard Desktop Duplication API (or whatever else you wire up), runs
its detector, and writes stick deflections. From the game's point of view,
a controller is plugged in.

This is the property that keeps the technique resilient across signature
updates: there is nothing to sign against.

---

## Install

```powershell
# 1. ViGEmBus driver (signed MSI). Reboot once after install.
#    https://github.com/nefarius/ViGEmBus/releases

# 2. Python deps
pip install pywin32 vgamepad

# 3. The library
git clone https://github.com/0xDI/game-input-bypass.git
cd game-input-bypass
pip install -e .
```

Verify the driver is loaded:

```powershell
Get-PnpDevice -FriendlyName "ViGEm*"
```

---

## Quick start

For production use, prefer `HumanizedGamepad`. It is a drop-in replacement
for `VirtualGamepad` with the same `(dx, dy)` pixel API:

```python
from game_input_bypass import HumanizedGamepad

pad = HumanizedGamepad(sensitivity=0.04, max_deflection=0.75)

# pixel error from your detector
pad.move(dx=12, dy=-4)

# primary fire (right trigger)
pad.click()

# return to neutral; tremor keeps emitting so the pad never reads as dead
pad.release()
```

Skeleton of an external aim loop:

```python
from game_input_bypass import HumanizedGamepad

pad = HumanizedGamepad()
CX, CY = 1920 // 2, 1080 // 2

while running:
    target = detector(capture.grab())     # your detector
    if target is None:
        pad.release()
        continue
    pad.move(target.x - CX, target.y - CY)
```

Full skeleton in [`examples/external_aim_loop.py`](examples/external_aim_loop.py).
Headless trace + correctness assertions in
[`examples/humanizer_trace.py`](examples/humanizer_trace.py).

---

## `HumanizedGamepad` — behavioral shaping

Five layers run every frame; they are not modes. The result is one
`set_stick(sx, sy)` call per frame whose trajectory carries all five
signatures together.

| Layer            | Mechanism                                                                                                                  |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Reaction delay   | New target (input jump > 60 px) gates output for a uniformly-distributed 80-150 ms hold                                    |
| Easing           | First-order low-pass approach with τ = 80 ms; computed from real `dt`, so identical motion at any loop rate                |
| Tremor           | 2-D Ornstein-Uhlenbeck process: `θ = 2π·8 Hz`, `σ = amplitude·√(2θ)` so stationary std equals the requested amplitude      |
| Overshoot        | On snaps > 120 px, desired deflection is amplified by 1.08 for 35 ms after the reaction hold ends, then settles            |
| Idle drift       | OU keeps stepping during `release()`; the pad never reads as a frozen stick between targets                                |

### Tuning

Every parameter is a keyword on the constructor. Defaults are calibrated for
a 1920×1080 detector at ~90° FoV.

```python
pad = HumanizedGamepad(
    sensitivity         = 0.04,
    max_deflection      = 0.75,
    reaction_ms_min     = 80,     reaction_ms_max  = 150,
    reaction_trigger_px = 60,
    easing_tau_ms       = 80,
    tremor_amplitude    = 0.006,  tremor_band_hz   = 8.0,
    overshoot_factor    = 1.08,   overshoot_ms     = 35,
    overshoot_trigger_px= 120,
    idle_drift          = True,
    seed                = None,   # set for reproducible output
    clock               = time.perf_counter,  # injectable for tests
)
```

### Verifying the curve

`examples/humanizer_trace.py` runs the humanizer against a *virtual* clock
with a mocked pad — no driver required — and prints summary statistics for
each phase. Sample run, seed = 42, 240 Hz:

```
  idle baseline          n= 240  mean=+0.0013  std=0.0060  min=-0.0154  max=+0.0189
  snap (reaction + pull) n=  30  mean=+0.0113  std=0.0392  min=-0.0185  max=+0.1622
  steady tracking        n= 240  mean=+0.7505  std=0.1109  min=+0.1997  max=+0.8208
  release decay          n= 240  mean=+0.0611  std=0.1433  min=-0.0165  max=+0.7612

checks passed: tremor present, tracking settles, release decays
```

Note that the idle phase standard deviation matches the configured
`tremor_amplitude=0.006` to four decimal places. The OU process is
calibrated so its *stationary* standard deviation equals the requested
amplitude — not approximately, by construction.

---

## `VirtualGamepad` — the injection bypass

The lower-level building block. Wraps `vgamepad`'s XInput emulator and adds
the three details that turn it from "an emulated pad" into "input the game
actually consumes":

- **Wake/prime on attach.** A non-zero stick deflection is emitted on
  construction. Some titles only switch their active input map after the
  first non-zero packet — without this they ignore the pad for the first
  few seconds.
- **`max_deflection` clamp.** Defaults to 0.80. A pegged stick (`±1.0`)
  trips every engine's snap-smoothing curve and produces visibly wrong
  motion. This single insight is the difference between "the pad works"
  and "the pad works *well*."
- **Dead zone.** Inside a 3 px radius (configurable) the stick is released
  to neutral. Continuously emitting micro-deflections produces visible
  judder in-engine.

Use directly if you want full control of the stick signal:

```python
from game_input_bypass import VirtualGamepad

pad = VirtualGamepad(sensitivity=0.035, max_deflection=0.80, dead_zone_px=3.0)
pad.move(dx, dy)         # pixel-space input → stick deflection
pad.set_stick(0.4, -0.1) # or write raw stick values directly
pad.click()
pad.left_trigger(1.0)    # ADS on most binds
```

---

## What is blocked, and why we don't use it

The methods you would reach for first, and the reason each one fails
against modern PC games:

| API / technique                                       | Blocked by                                                                                                      |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `user32!SendInput`                                    | Carries `LLMHF_INJECTED`. Filtered by every UE5 title and most modern FPS engines.                              |
| `user32!keybd_event`                                  | Same flag, same outcome.                                                                                        |
| `user32!mouse_event` (relative deltas)                | Accepted by Source/Source 2-era titles but ignored or smoothed-to-zero by UE5 / modern engines.                 |
| `user32!SetCursorPos` / `mouse_event` absolute moves  | FPS engines read raw `WM_INPUT` deltas, not cursor position. The warp is simply ignored in-game.                |
| DirectInput keyboard/mouse                            | Microsoft-deprecated since Win8. Modern engines do not poll it.                                                 |
| `PostMessage(WM_MOUSEMOVE, …)`                        | Engines hook `WM_INPUT`, not `WM_MOUSEMOVE`. The message arrives, the game does nothing with it.                |
| DLL injection / API hooking inside the game           | Trips every anti-cheat that scans for unsigned modules. Also defeats the "external" property of this project.   |
| Reading/writing game memory                           | Same problem, much louder.                                                                                      |

What is **not** blocked, and what this library uses:

| Technique                                | Why it still works                                                                                                                                              |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| XInput packets via ViGEmBus virtual pad  | ViGEmBus is signed by Microsoft and exposes a real HID device to the kernel. The packets are indistinguishable from a real Xbox controller's at the engine level. |

---

## How it works end-to-end

```
┌─────────────────────────────────────────────────────────────────┐
│                  your external cheat process                    │
│                                                                 │
│   screen capture → detector → target (x, y)                     │
│                                  │                              │
│                                  ▼                              │
│              ┌──────────────────────────────────┐               │
│              │ HumanizedGamepad                 │               │
│              │   reaction · easing · tremor     │               │
│              │   overshoot · idle drift         │               │
│              └─────────────┬────────────────────┘               │
│                            │ set_stick(sx, sy)                  │
│                            ▼                                    │
│              ┌──────────────────────────────────┐               │
│              │ VirtualGamepad (vgamepad)        │               │
│              └─────────────┬────────────────────┘               │
└────────────────────────────┼────────────────────────────────────┘
                             │ user-mode IOCTL
                             ▼
                ┌──────────────────────────────┐
                │  ViGEmBus.sys (MS-signed)    │
                │  publishes a virtual XInput  │
                │  HID controller              │
                └──────────────┬───────────────┘
                               │ XInput / Raw HID
                               ▼
                       ┌──────────────┐
                       │  target game │
                       └──────────────┘
```

### Stick model

The right stick is driven as a **velocity vector**, not a position.
Screen-space pixel error `(dx, dy)` is mapped to the unit square:

```
stick_x =  clamp(dx * sensitivity, ±max_deflection)
stick_y = -clamp(dy * sensitivity, ±max_deflection)   # screen Y is inverted
```

`HumanizedGamepad` then runs the deflection through its five-layer shaping
pipeline before calling `VirtualGamepad.set_stick()`.

---

## Supported games

Verified to receive virtual-pad input as if from a real controller, **and**
to be undetected on this technique as of **May 2026**:

| Title             | Engine                | Status      |
| ----------------- | --------------------- | ----------- |
| Fortnite          | UE5                   | undetected  |
| Apex Legends      | modified Source       | undetected  |
| The Finals        | UE5                   | undetected  |
| FragPunk          | UE5                   | undetected  |

Adding a title is one tuple entry in `game_input_bypass/detect.py`. The
gamepad itself works regardless — `detect_game()` only exists so consumers
can branch on which profile (sensitivity, smoothing) to load.

> **Out of scope.** Kernel anti-cheat titles (Valorant / Vanguard, Faceit /
> ESEA, modern CoD / Ricochet, EA Javelin). Vanguard in particular scans
> the driver list and refuses to launch if ViGEmBus is loaded. This library
> does not attempt to defeat that.

---

## Project layout

```
game-input-bypass/
├── game_input_bypass/
│   ├── __init__.py        public re-exports
│   ├── gamepad.py         VirtualGamepad — the injection bypass
│   ├── humanizer.py       HumanizedGamepad — the behavioral bypass
│   └── detect.py          foreground-window classifier
├── examples/
│   ├── smoke_test.py
│   ├── external_aim_loop.py
│   └── humanizer_trace.py headless trace + correctness checks
├── pyproject.toml
├── requirements.txt
├── CHANGELOG.md
├── LICENSE
└── README.md
```

---

## FAQ

**Will this ever be patched?**
The ViGEmBus driver is Microsoft-signed and ships in too many legitimate
products (Steam Input, DS4Windows, reWASD, the Xbox Accessories app) for
any sane anti-cheat vendor to blacklist outright. The remaining attack
surface is behavioral — looking for too-perfect stick curves, missing
tremor, suspicious reaction times — and that surface is exactly what
`HumanizedGamepad` addresses.

**Can the game tell my "mouse aim" is actually a controller?**
On supported titles the engine internally treats the stick input as a
controller, including applying its own native aim assist on top. That is
a feature, not a bug.

**Why Python?**
The bottleneck is the screen-capture + detector stage, not the input stage.
The input call costs one IOCTL — language overhead is irrelevant. Port to
C++ if you want; the surface area is small.

**Does it work over Easy Anti-Cheat / BattlEye?**
At the time of writing, yes, on the listed titles. Neither vendor currently
flags ViGEmBus presence. Track `CHANGELOG.md` for status changes.

**How is the humanizer's tremor "physiological"?**
The 6-12 Hz band is the documented action-tremor frequency of the human
upper limb. The OU process produces band-limited noise with a known
stationary distribution, so the parameters map directly to observables:
`tremor_amplitude` *is* the resulting standard deviation, and
`tremor_band_hz` *is* the spectral roll-off point. Defaults match published
measurements; tune to taste.

---

## Disclaimer

This repository is published for **educational and research purposes only**.

It documents how Windows input APIs and signed HID virtualisation drivers
behave when used as designed, and how to shape the resulting signal so it
carries the statistical signatures of human input. Using the code to gain
an unfair advantage in multiplayer games is likely to violate the terms of
service of those games and may result in account or hardware bans. The
authors do not endorse such use and accept no liability for it.

---

## License

MIT — see [LICENSE](LICENSE).
