# -*- coding: utf-8 -*-
"""NexaTrans UI v2.0 - theme + reusable animated widget kit."""

from ui.theme import Palette, Radius, Space, Motion, apply_app_theme, ui_font
from ui.widgets.anim import animate, stop_animation
from ui.widgets.buttons import GlowButton, IconButton
from ui.widgets.containers import Card, LogoMark, SlideStack, TitleBar
from ui.widgets.controls import NeonSlider, ToggleSwitch
from ui.widgets.feedback import (
    SliderRow, Spinner, StatChip, StatusPill, Toast, ToggleRow,
)

__all__ = [
    "Palette", "Radius", "Space", "Motion", "apply_app_theme", "ui_font",
    "animate", "stop_animation",
    "GlowButton", "IconButton",
    "Card", "LogoMark", "SlideStack", "TitleBar",
    "NeonSlider", "ToggleSwitch",
    "SliderRow", "Spinner", "StatChip", "StatusPill", "Toast", "ToggleRow",
]
