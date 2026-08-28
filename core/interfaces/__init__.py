"""Engine Interfaces for AI News Studio.

Aggregates abstract interface classes for all components.
"""

from core.interfaces.voice import VoiceEngine
from core.interfaces.presenter import PresenterEngine
from core.interfaces.director import DirectorEngine
from core.interfaces.broll import BrollEngine
from core.interfaces.motion import MotionEngine
from core.interfaces.lipsync import LipSyncEngine
from core.interfaces.editor import EditorEngine
from core.interfaces.caption import CaptionEngine
from core.interfaces.export import ExportEngine

__all__ = [
    "VoiceEngine",
    "PresenterEngine",
    "DirectorEngine",
    "BrollEngine",
    "MotionEngine",
    "LipSyncEngine",
    "EditorEngine",
    "CaptionEngine",
    "ExportEngine",
]
