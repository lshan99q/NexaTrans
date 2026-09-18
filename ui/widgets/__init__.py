# -*- coding: utf-8 -*-
"""NexaTrans UI - Windows 11 Fluent design system + widget kit."""

from ui.theme import (
    DARK, LIGHT, MODE_DARK, MODE_LIGHT, MODE_LABELS, MODE_SYSTEM, Motion,
    Radius, Space, Tokens, apply_app_theme, current_mode, is_dark, mix, qc,
    qss, rounded_path, set_theme_mode, shadow_pixmap, theme, ui_font,
)
from ui.widgets.anim import animate, stop_animation
from ui.widgets.buttons import CaptionButton, FluentButton, IconButton
from ui.widgets.containers import (
    Card, Divider, FluentStack, LogoMark, SettingsRow, TitleBar,
)
from ui.widgets.controls import FluentSlider, ToggleSwitch
from ui.widgets.feedback import (
    InfoBar, MetricTile, ProgressRing, StatusBadge,
)

__all__ = [
    # theme
    "DARK", "LIGHT", "Tokens", "Motion", "Radius", "Space",
    "MODE_SYSTEM", "MODE_LIGHT", "MODE_DARK", "MODE_LABELS",
    "theme", "set_theme_mode", "apply_app_theme", "current_mode", "is_dark",
    "qc", "qss", "mix", "ui_font", "rounded_path", "shadow_pixmap",
    # animation
    "animate", "stop_animation",
    # widgets
    "FluentButton", "IconButton", "CaptionButton",
    "Card", "SettingsRow", "Divider", "LogoMark", "TitleBar", "FluentStack",
    "ToggleSwitch", "FluentSlider",
    "InfoBar", "ProgressRing", "StatusBadge", "MetricTile",
]
