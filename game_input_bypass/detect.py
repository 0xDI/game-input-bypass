"""Foreground-window classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

import win32gui


@dataclass(frozen=True)
class GameProfile:
    key: str
    channel: str            # "gamepad" | "mouse_event"
    title_needles: Tuple[str, ...]


# Order matters: first match wins.
_PROFILES: Tuple[GameProfile, ...] = (
    GameProfile("fortnite",       "gamepad",     ("fortnite",)),
    GameProfile("csgo",           "mouse_event", ("counter-strike", "cs:go",
                                                  "cs2", "counter-strike 2",
                                                  "counter-strike: global offensive")),
    GameProfile("apex",           "gamepad",     ("apex legends",)),
    GameProfile("valorant",       "mouse_event", ("valorant",)),
    GameProfile("source_classic", "mouse_event", ("half-life", "team fortress",
                                                  "left 4 dead", "portal")),
)


def _foreground_title() -> str:
    try:
        return win32gui.GetWindowText(win32gui.GetForegroundWindow()).lower()
    except Exception:
        return ""


def detect_game(title: Optional[str] = None) -> Optional[GameProfile]:
    """Return the matching profile for `title`, or for the foreground window."""
    t = (title or _foreground_title()).lower()
    if not t:
        return None
    for p in _PROFILES:
        if any(n in t for n in p.title_needles):
            return p
    return None


def preferred_channel(profile: GameProfile | str | None) -> str:
    """Resolve a profile (object or key) to its channel name."""
    if profile is None:
        return "mouse_event"
    if isinstance(profile, GameProfile):
        return profile.channel
    for p in _PROFILES:
        if p.key == profile:
            return p.channel
    return "mouse_event"


def iter_profiles() -> Iterable[GameProfile]:
    return iter(_PROFILES)
