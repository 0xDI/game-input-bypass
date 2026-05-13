"""External input delivery via a Microsoft-signed virtual HID controller.

Public API:
    VirtualGamepad   ViGEmBus-backed XInput 360 pad
    detect_game      classify the foreground window
    GameProfile      profile dataclass
"""

from .gamepad import VirtualGamepad
from .detect import detect_game, GameProfile, iter_profiles

__all__ = ["VirtualGamepad", "detect_game", "GameProfile", "iter_profiles"]
__version__ = "0.2.0"
