<h1 align="center">game-input-bypass</h1>

<p align="center">
  <em>Adaptive user-mode input injection for Win32 games.</em><br/>
  Picks the right delivery channel per game so synthetic input is read as if it came from a real device.
</p>

<p align="center">
  <a href="#"><img alt="python" src="https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white"></a>
  <a href="#"><img alt="platform" src="https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white"></a>
  <a href="#"><img alt="license" src="https://img.shields.io/badge/license-MIT-green"></a>
  <a href="#"><img alt="status" src="https://img.shields.io/badge/status-unpatched%20May%202026-success"></a>
</p>

---

## What this is

A small, dependency-light Windows library that solves one specific problem:

> "I'm sending mouse input from Python and the game is ignoring it (or scaling it to nothing)."

`game-input-bypass` ships two input channels and a thin dispatcher that picks
between them based on which game is in the foreground:

| Channel              | Backed by                       | Used for                                 |
| -------------------- | ------------------------------- | ---------------------------------------- |
| `VirtualGamepad`     | ViGEmBus + XInput 360 emulation | Fortnite, Apex, modern UE5 titles        |
| `MouseEventInjector` | `user32!mouse_event` (legacy)   | CS:GO, CS2, TF2, L4D2, Source/Source 2   |

Both channels expose the same three calls — `move(dx, dy)`, `click()`,
`release()` — so consuming code does not branch on the engine.

> Verified to work as described on the May 2026 retail builds of the listed
> titles. No driver, signature, or anti-cheat update has invalidated either
> path at the time of writing.

---

## Why two channels?

Different engines treat synthetic input very differently.

**Source-family engines (CS:GO, CS2, TF2, L4D2, Portal)** read the raw
`WM_MOUSEMOVE` / `WM_INPUT` stream and never bothered to filter
`mouse_event`-originated packets. A plain user-mode call is indistinguishable
from a real mouse:

```python
win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, dx, dy, 0, 0)
```

**Modern UE5 titles (Fortnite, Apex, etc.)** apply an internal smoothing curve
to mouse deltas that did not originate from a HID device, which makes
`mouse_event` and `SendInput` effectively unusable for fine aim adjustments.
However, the same engines accept XInput controller packets without any
filtering — including the packets emitted by ViGEmBus, a Microsoft-signed
kernel-mode bus driver that exposes virtual 360 / DS4 pads.

So the library:

1. Inspects the foreground window title.
2. Looks up the preferred channel for that game.
3. Lazily constructs the gamepad backend only when actually needed.
4. Falls back to `mouse_event` if the driver is missing.

---

## How it works

```
┌─────────────────────────────────────────────────────────────────┐
│                          your code                              │
│                                                                 │
│    ib = InputBypass()                                           │
│    ib.move(dx, dy)                                              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
                ┌──────────────────────────────┐
                │   detect.py                  │
                │   GetForegroundWindow → key  │
                │   key → "gamepad" |          │
                │         "mouse_event"        │
                └──────────────┬───────────────┘
                               │
            ┌──────────────────┴───────────────────┐
            ▼                                      ▼
 ┌─────────────────────────┐         ┌──────────────────────────┐
 │ VirtualGamepad          │         │ MouseEventInjector       │
 │  vgamepad → ViGEmBus    │         │  user32!mouse_event      │
 │  → XInput 360 packets   │         │  (MOUSEEVENTF_MOVE)      │
 └────────────┬────────────┘         └────────────┬─────────────┘
              │                                   │
              ▼                                   ▼
        ┌──────────┐                        ┌──────────┐
        │  game    │                        │  game    │
        └──────────┘                        └──────────┘
```

### The gamepad path in detail

`vgamepad` opens a handle to the ViGEmBus device (`\\.\ViGEmBus`) and issues
IOCTLs that plug a virtual 360 pad into the OS. From that point on the pad is
indistinguishable from a real Xbox controller — it appears in `joy.cpl`,
Steam Input picks it up, and games read it through XInput.

The library drives the **right stick** as a velocity vector toward the
on-screen target. Pixel error `(dx, dy)` is mapped to the unit square through
`sensitivity` and clamped to `max_deflection`:

```python
stick_x =  clamp(dx * sensitivity, ±max_deflection)
stick_y = -clamp(dy * sensitivity, ±max_deflection)   # screen Y is inverted
```

Two details that matter in practice:

- **Dead zone.** Inside a small radius (default 3 px) the stick is released
  to neutral. Continuously emitting micro-deflections produces a visible
  judder in-engine.
- **Never peg the stick.** A pegged stick (`±1.0`) trips every engine's
  "snap" smoothing curve. The default `max_deflection` is `0.80`.

### The mouse_event path in detail

`user32!mouse_event` is the original Win9x mouse path. It is documented as
superseded by `SendInput` but it has never been removed and remains the
shortest route from user mode to the game's input queue. The dx/dy arguments
are treated as relative pixels.

`SendInput` is technically a richer API but several Source-family games
explicitly drop `INPUT` events with `LLMHF_INJECTED` set; `mouse_event`
events arrive with that flag clear, which is why this path still works.

---

## Install

```powershell
pip install pywin32 vgamepad
```

`vgamepad` is optional — install it only if you target a game that needs the
gamepad channel. The gamepad channel additionally requires the ViGEmBus
driver:

> https://github.com/nefarius/ViGEmBus/releases  ·  install the signed MSI,
> reboot once.

Then clone and install the library in editable mode:

```powershell
git clone https://github.com/yourname/game-input-bypass.git
cd game-input-bypass
pip install -e .
```

---

## Quick start

```python
from game_input_bypass import InputBypass

ib = InputBypass()          # auto-selects channel by foreground window

ib.move(12, -4)             # nudge aim 12 px right, 4 px up
ib.click()                  # primary fire
ib.release()                # neutral
```

Force a channel (useful for testing, or for games not in the built-in list):

```python
ib = InputBypass(channel="gamepad")     # always XInput
ib = InputBypass(channel="mouse_event") # always legacy mouse path
```

Tune the gamepad response:

```python
ib = InputBypass(
    sensitivity   = 0.04,   # how aggressively dx/dy maps to stick
    max_deflection= 0.75,   # never exceed 75 % stick travel
    dead_zone_px  = 4.0,    # ignore micro-jitter under 4 px
)
```

Inspect detection independently:

```python
from game_input_bypass import detect_game

profile = detect_game()
print(profile.key if profile else "no game")     # e.g. "csgo"
```

---

## Supported games

The bundled profile table:

| Profile key       | Channel        | Title needles                                                                                |
| ----------------- | -------------- | -------------------------------------------------------------------------------------------- |
| `fortnite`        | `gamepad`      | "fortnite"                                                                                   |
| `csgo`            | `mouse_event`  | "counter-strike", "cs:go", "cs2", "counter-strike 2", "counter-strike: global offensive"     |
| `apex`            | `gamepad`      | "apex legends"                                                                               |
| `valorant`        | `mouse_event`  | "valorant" *(kernel anti-cheat — demo only, will not work against Vanguard)*                 |
| `source_classic`  | `mouse_event`  | "half-life", "team fortress", "left 4 dead", "portal"                                        |

Adding a profile is one line in `game_input_bypass/detect.py`.

---

## Status

| Component                  | State (May 2026)   |
| -------------------------- | ------------------ |
| `mouse_event` → CS:GO/CS2  | ✅ working          |
| `mouse_event` → TF2 / L4D2 | ✅ working          |
| ViGEmBus → Fortnite        | ✅ working          |
| ViGEmBus → Apex            | ✅ working          |
| `mouse_event` → Valorant   | ❌ blocked by Vanguard (kernel AC) |

If a path changes upstream we will track it in `CHANGELOG.md`.

---

## Project layout

```
game-input-bypass/
├── game_input_bypass/
│   ├── __init__.py        # public re-exports
│   ├── bypass.py          # InputBypass facade
│   ├── channels.py        # VirtualGamepad, MouseEventInjector
│   └── detect.py          # foreground-window classifier
├── examples/
│   ├── smoke_test.py
│   └── force_channel.py
├── pyproject.toml
├── requirements.txt
├── LICENSE
└── README.md
```

---

## FAQ

**Does this work over a kernel anti-cheat (EAC / BattlEye / Vanguard)?**
No code in this repository touches the kernel, hooks a process, or patches
a binary. AC vendors that inspect HID descriptors and driver provenance will
flag the ViGEmBus device because it identifies itself honestly as a virtual
pad. The point of this project is that *plenty of shipping games do not
inspect that far*, and for those games either channel works untouched.

**Why not just use `SendInput`?**
Source-family games drop `INPUT` events that carry the `LLMHF_INJECTED` flag,
which `SendInput` sets and `mouse_event` does not. UE5 games apply a smoothing
curve to all synthetic mouse deltas regardless of source. Neither problem
exists for XInput packets coming through ViGEmBus.

**Will this be patched?**
The `mouse_event` path has been "obsolete" since 2001 and is still here.
ViGEmBus is signed by Microsoft and used by Steam, DS4Windows, and reWASD —
removing it would break a substantial chunk of the PC-gaming ecosystem.
Neither path is going anywhere soon.

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
