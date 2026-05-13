"""External input delivery via a Microsoft-signed virtual HID controller.

Public API:
    VirtualGamepad     ViGEmBus-backed XInput 360 pad (raw)
    HumanizedGamepad   Behavioral-shaping wrapper (recommended)
    detect_game        Classify the foreground window
    GameProfile        Profile dataclass
"""

from .gamepad import VirtualGamepad
from .humanizer import HumanizedGamepad
from .detect import detect_game, GameProfile, iter_profiles

__all__ = [
    "VirtualGamepad",
    "HumanizedGamepad",
    "detect_game",
    "GameProfile",
    "iter_profiles",
]
__version__ = "0.3.0"
