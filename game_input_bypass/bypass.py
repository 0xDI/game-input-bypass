"""High-level facade combining detection + channel dispatch."""

from __future__ import annotations

import logging
from typing import Optional

from .channels import Channel, MouseEventInjector, VirtualGamepad
from .detect import detect_game, preferred_channel

log = logging.getLogger(__name__)


class InputBypass:
    """Pick the appropriate channel for the active foreground game.

    The gamepad backend is lazily instantiated on first use so that consumers
    on machines without ViGEmBus do not pay the import cost (or fail at import
    time) unless they actually target a game that needs it.

    Parameters
    ----------
    channel:
        Force a specific channel ('gamepad' or 'mouse_event'). When None
        (default), the channel is selected per-call from the foreground
        window title.
    **gamepad_kwargs:
        Forwarded to :class:`VirtualGamepad` on first construction.
    """

    def __init__(self, channel: Optional[str] = None, **gamepad_kwargs) -> None:
        self._forced = channel
        self._gamepad_kwargs = gamepad_kwargs
        self._gamepad: Optional[VirtualGamepad] = None
        self._mouse: Channel = MouseEventInjector()
        self._last_profile_key: Optional[str] = None

    # ── channel selection ────────────────────────────────────────────────
    def _select_channel_name(self) -> str:
        if self._forced is not None:
            return self._forced
        profile = detect_game()
        key = profile.key if profile else None
        if key != self._last_profile_key:
            log.info("active profile: %s", key or "unknown")
            self._last_profile_key = key
        return preferred_channel(profile)

    def _gamepad_or_fallback(self) -> Channel:
        if self._gamepad is not None:
            return self._gamepad
        try:
            self._gamepad = VirtualGamepad(**self._gamepad_kwargs)
            log.info("ViGEm gamepad attached")
            return self._gamepad
        except Exception as exc:
            log.warning("ViGEm unavailable (%s); using mouse_event", exc)
            return self._mouse

    def _channel(self) -> Channel:
        return (self._gamepad_or_fallback()
                if self._select_channel_name() == "gamepad"
                else self._mouse)

    # ── public API ───────────────────────────────────────────────────────
    def move(self, dx: float, dy: float) -> None:
        self._channel().move(dx, dy)

    def click(self, hold_ms: int = 10) -> None:
        self._channel().click(hold_ms)

    def release(self) -> None:
        if self._gamepad is not None:
            self._gamepad.release()
