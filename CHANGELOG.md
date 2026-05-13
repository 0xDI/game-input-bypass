# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2026-05-13
### Added
- **`HumanizedGamepad`** — behavioral shaping layer that wraps
  `VirtualGamepad`. Drop-in replacement that adds physiological tremor
  (Ornstein-Uhlenbeck process tuned to the 6-12 Hz action-tremor band),
  exponential easing toward target, reaction-delay gating on new targets,
  overshoot-and-correct on large snaps, and idle drift so the controller
  never reads as a frozen stick.
- `VirtualGamepad.set_stick(sx, sy)` — raw normalized stick setter used by
  shaping layers that compute deflection themselves.
- `VirtualGamepad.left_trigger(value)` — ADS / scope pull on most binds.
- Injected `clock` parameter on `HumanizedGamepad` for deterministic,
  driver-less testing.
- `examples/humanizer_trace.py` — headless trace + assertions that verify
  the four characteristic phases (idle / snap / track / release).

## [0.2.0] - 2026-05-13
### Changed
- **Scope refocus.** Project is now strictly an external, fully user-mode
  delivery layer built on a Microsoft-signed virtual HID controller. The
  `mouse_event` channel and Source / Source 2 / Valorant profiles were
  removed — those targets do not require a bypass and were diluting the
  point of the project.
- `InputBypass` facade removed; the library now exposes `VirtualGamepad`
  directly.
- README rewritten to document the external-cheat use case and current
  detection status (undetected, May 2026).
- Bundled profiles narrowed to titles where the technique is verified and
  required: Fortnite, Apex Legends, The Finals, FragPunk.
### Removed
- `MouseEventInjector`, `bypass.py`, CS:GO / CS2 / Source / Valorant profiles.
- `examples/force_channel.py` (channel selection no longer applies).

## [0.1.0] - 2026-05-13
### Added
- Initial release.
- `MouseEventInjector` channel for Source/Source 2 era titles.
- `VirtualGamepad` channel backed by ViGEmBus for UE5 titles.
- `InputBypass` dispatcher with foreground-window detection.
- Profiles for Fortnite, CS:GO/CS2, Apex, Valorant, classic Source games.
- Example scripts: `smoke_test.py`, `force_channel.py`.
