"""Adaptive user-mode input injection for Win32 games.

Public API:

    InputBypass         high-level facade, picks channel by foreground window
    VirtualGamepad      ViGEmBus-backed XInput 360 pad
    MouseEventInjector  legacy user32!mouse_event path
    detect_game         classify the foreground window
    preferred_channel   look up the channel for a profile key
"""

from .channels import VirtualGamepad, MouseEventInjector
from .detect import detect_game, preferred_channel, GameProfile
from .bypass import InputBypass

__all__ = [
    "InputBypass",
    "VirtualGamepad",
    "MouseEventInjector",
    "detect_game",
    "preferred_channel",
    "GameProfile",
]

__version__ = "0.1.0"
