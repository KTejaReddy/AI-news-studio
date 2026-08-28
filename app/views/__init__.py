"""Views package for AI News Studio.

Aggregates all distinct modular sub-frames used inside the application viewport.
"""

from app.views.dashboard import DashboardView
from app.views.projects import ProjectsView
from app.views.presenters import PresentersView
from app.views.voices import VoicesView
from app.views.director import DirectorView
from app.views.broll import BrollView
from app.views.editor import EditorView
from app.views.settings import SettingsView
from app.views.models import ModelsView
from app.views.logs import LogsView
from app.views.production import ProductionView

__all__ = [
    "DashboardView",
    "ProjectsView",
    "PresentersView",
    "VoicesView",
    "DirectorView",
    "BrollView",
    "EditorView",
    "SettingsView",
    "ModelsView",
    "LogsView",
    "ProductionView",
]
