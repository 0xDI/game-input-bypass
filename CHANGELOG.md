# Changelog

All notable changes to this project will be documented in this file.

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
