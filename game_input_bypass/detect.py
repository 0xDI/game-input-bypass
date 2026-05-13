"""Foreground-window classification.

Only titles where the virtual-gamepad path is verified to defeat synthetic-
input filtering are listed. Adding a profile is one entry in `_PROFILES`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

import win32gui


@dataclass(frozen=True)
class GameProfile:
    key: str
    title_needles: Tuple[str, ...]


# Targets whose engines filter `LLMHF_INJECTED` mouse input but accept XInput.
_PROFILES: Tuple[GameProfile, ...] = (
    GameProfile("fortnite",         ("fortnite",)),
    GameProfile("apex_legends",     ("apex legends",)),
    GameProfile("fragpunk",         ("fragpunk",)),
    GameProfile("the_finals",       ("the finals",)),
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


def iter_profiles() -> Iterable[GameProfile]:
    return iter(_PROFILES)
