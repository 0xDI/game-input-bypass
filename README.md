<h1 align="center">game-input-bypass</h1>

<p align="center">
  <em>External, fully user-mode input delivery for Win32 games that filter synthetic input.</em><br/>
  No DLL injection. No process hooks. No memory access. Just a Microsoft-signed virtual HID controller.
</p>

<p align="center">
  <a href="#"><img alt="python"     src="https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white"></a>
  <a href="#"><img alt="platform"   src="https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white"></a>
  <a href="#"><img alt="license"    src="https://img.shields.io/badge/license-MIT-green"></a>
  <a href="#"><img alt="status"     src="https://img.shields.io/badge/status-undetected%20%E2%80%94%20May%202026-success"></a>
  <a href="#"><img alt="invasive"   src="https://img.shields.io/badge/process%20touched-none-informational"></a>
</p>

---

## What this is

A **fully external** input library for Windows games that filter synthetic
mouse input. It is meant to be the *output stage* of an external cheat — i.e.
the part that turns a target coordinate computed in one of your own processes
into in-game aim movement that the target engine accepts.

The library does exactly one thing well: it presents a Microsoft-signed
virtual Xbox 360 controller to the OS through the **ViGEmBus** kernel driver
and drives its right stick toward a screen-space target. Because the device
is a real HID controller from the kernel's perspective, the packets it emits
carry none of the synthetic-input markers (`LLMHF_INJECTED`,
non-HID `RAWINPUTHEADER.hDevice`, etc.) that modern engines use to drop
software-generated mouse events.

> **Status — May 2026: undetected.**
> No detection of this technique has been reported on any of the supported
> titles at the time of writing. The ViGEmBus driver itself is signed by
> Microsoft and used by Steam Input, DS4Windows, reWASD, and the Xbox
> Accessories app, so flagging it would break a substantial chunk of the
> legitimate PC-gaming ecosystem.

---

## Why this approach

Every "obvious" way to send mouse input from an external process is filtered
by modern PC games. This is the table you would otherwise have to learn by
hand:

| API / technique                              | Blocked by                                                                                                              |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `user32!SendInput`                           | Events carry `LLMHF_INJECTED`. Filtered by every UE5 title and most modern FPS engines.                                 |
| `user32!keybd_event`                         | Same flag, same outcome.                                                                                                |
| `user32!mouse_event`                         | Accepted by Source/Source 2 era titles but ignored or smoothed-to-zero by UE5 / modern engines.                         |
| `user32!SetCursorPos`                        | Most FPS engines read raw `WM_INPUT` deltas, not cursor position. The warp is simply ignored in-game.                   |
| DirectInput keyboard/mouse                   | Microsoft-deprecated since Win8. Modern engines do not poll it.                                                         |
| `PostMessage(WM_MOUSEMOVE, …)`               | Engines hook `WM_INPUT`, not `WM_MOUSEMOVE`. The message arrives, the game does nothing with it.                        |
| DLL injection / API hooking inside the game  | Trips every anti-cheat that scans for unsigned modules in the process image. Also defeats the "external" property.       |
| Reading/writing game memory                  | Same problem, much louder.                                                                                              |

What is **not** blocked, and what this library uses:

| Technique                                  | Why it still works                                                                                                                                              |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| XInput packets via ViGEmBus virtual pad    | ViGEmBus is signed by Microsoft and exposes a real HID device to the kernel. The packets are indistinguishable from a real Xbox controller's at the engine level. |

---

## What "external" means here

> Nothing in this library touches the target game.

- No `OpenProcess`, no `ReadProcessMemory`, no `WriteProcessMemory`.
- No DLL injection, no `CreateRemoteThread`, no manual mapping.
- No `SetWindowsHookEx` against the game's threads.
- No driver of our own. ViGEmBus is a third-party Microsoft-signed driver
  installed system-wide by the user.

The cheat process runs in its own address space, captures the screen with
the standard Desktop Duplication API (or whatever you wire up), runs its
detector, and pushes a stick deflection. From the game's point of view, a
controller is plugged in.

This is the property that keeps the technique undetected across signature
updates: there is nothing to sign against.

---

## How it works

```
┌─────────────────────────────────────────────────────────────────┐
│                    your external cheat process                  │
│                                                                 │
│   screen capture → detector → target (x, y) → pad.move(dx,dy)   │
└───────────────────────────────┬─────────────────────────────────┘
                                │  user-mode IOCTL
                                ▼
                ┌──────────────────────────────┐
                │  vgamepad (pip)              │
                │  vigem_client.dll            │
                └──────────────┬───────────────┘
                               │  \\.\ViGEmBus
                               ▼
                ┌──────────────────────────────┐
                │  ViGEmBus.sys (MS-signed)    │
                │  publishes a virtual XInput  │
                │  HID controller              │
                └──────────────┬───────────────┘
                               │  XInput / Raw HID
                               ▼
                       ┌──────────────┐
                       │  target game │
                       └──────────────┘
```

### Stick model

The right stick is driven as a **velocity vector**, not a position. Screen-
space pixel error `(dx, dy)` is mapped to the unit square:

```python
stick_x =  clamp(dx * sensitivity, ±max_deflection)
stick_y = -clamp(dy * sensitivity, ±max_deflection)   # screen Y is inverted
```

Two details that matter in practice:

- **Dead zone.** Inside a small radius (default 3 px) the stick is released
  to neutral. Continuously emitting micro-deflections produces a visible
  judder.
- **Never peg the stick.** `max_deflection` defaults to `0.80`; a pegged
  stick (`±1.0`) trips every engine's "snap" smoothing curve.

---

## Install

```powershell
# 1. Install the ViGEmBus driver, signed MSI, reboot once:
#    https://github.com/nefarius/ViGEmBus/releases

# 2. Python deps
pip install pywin32 vgamepad

# 3. The library itself
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

```python
from game_input_bypass import VirtualGamepad

pad = VirtualGamepad(sensitivity=0.04, max_deflection=0.75)

# pixel error from your detector
pad.move(dx=12, dy=-4)

# primary fire (right trigger)
pad.click()

# back to neutral
pad.release()
```

Integration sketch for an external cheat:

```python
from game_input_bypass import VirtualGamepad

pad = VirtualGamepad()

while running:
    frame      = capture.grab()              # your screen capture
    target     = detector(frame)             # your model / heuristic
    if target is None:
        pad.release()
        continue
    dx = target.x - screen_w // 2
    dy = target.y - screen_h // 2
    pad.move(dx, dy)
```

See [`examples/external_aim_loop.py`](examples/external_aim_loop.py) for a
runnable skeleton.

---

## Supported games

Verified to receive virtual-pad input as if from a real controller, **and**
to be undetected on this technique as of **May 2026**:

| Title             | Engine          | Status      |
| ----------------- | --------------- | ----------- |
| Fortnite          | UE5             | undetected  |
| Apex Legends      | mod. Source     | undetected  |
| The Finals        | UE5             | undetected  |
| FragPunk          | UE5             | undetected  |

Adding a title is one tuple entry in `game_input_bypass/detect.py`. The
gamepad itself works regardless — `detect_game()` only exists so consumers
can branch on which profile (sensitivity, smoothing) to load.

> **Out of scope:** kernel anti-cheat titles (Valorant / Vanguard, Faceit /
> ESEA, modern CoD / Ricochet, EA Javelin). Vanguard in particular scans the
> driver list and will refuse to launch if ViGEmBus is loaded. This library
> does not attempt to defeat that — it would require a different project
> entirely.

---

## Project layout

```
game-input-bypass/
├── game_input_bypass/
│   ├── __init__.py        public re-exports
│   ├── gamepad.py         VirtualGamepad
│   └── detect.py          foreground-window classifier
├── examples/
│   ├── smoke_test.py
│   └── external_aim_loop.py
├── pyproject.toml
├── requirements.txt
├── LICENSE
└── README.md
```

---

## FAQ

**Will this ever be patched?**
The ViGEmBus driver is Microsoft-signed and ships in too many legitimate
products (Steam Input, DS4Windows, reWASD, the Xbox Accessories app) for any
sane anti-cheat vendor to blacklist outright. Detection would have to
happen *behaviourally* — looking for too-perfect stick curves, missing
mechanical jitter, etc. The mitigations against that are out of scope here
but are well-trodden ground.

**Can the game tell my "mouse aim" is actually a controller?**
On supported titles the engine internally treats your stick input as a
controller, including applying its own native aim assist to it. That is a
feature, not a bug.

**Why Python?**
Because the bottleneck is the screen-capture + detector stage, not the input
stage. The input call takes one IOCTL — language overhead is irrelevant.
Port to C++ if you want; the surface area is small.

**Does it work over Easy Anti-Cheat / BattlEye?**
At the time of writing, yes, on the listed titles. Neither vendor currently
flags ViGEmBus presence. This may change — track `CHANGELOG.md`.

---

## Disclaimer

This repository is published for **educational and research purposes only**.

It documents how Windows input APIs and signed HID virtualisation drivers
behave when used as designed. Using the code to gain an unfair advantage in
multiplayer games is likely to violate the terms of service of those games
and may result in account or hardware bans. The authors do not endorse such
use and accept no liability for it.

---

## License

MIT — see [LICENSE](LICENSE).
