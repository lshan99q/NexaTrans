# -*- coding: utf-8 -*-
"""
NexaTrans - tiny animation helpers.

``animate()`` gives every widget a named slot for a value animation, so
re-triggering the same slot safely cancels the previous run instead of
stacking animations on top of each other.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QVariantAnimation


def animate(owner, key: str, start, end, setter, duration: int = 220,
            easing: QEasingCurve.Type = QEasingCurve.OutCubic,
            finished=None) -> QVariantAnimation:
    """
    Run (or restart) the animation stored on ``owner`` under ``key``.

    ``setter`` receives every interpolated value.  Values keep the python
    type of ``start``/``end`` (int stays int, which matters for ``move()``).
    """
    store = owner.__dict__.setdefault("_nx_anims", {})
    previous = store.get(key)
    if isinstance(previous, QVariantAnimation):
        try:
            previous.stop()
        except RuntimeError:
            pass

    anim = QVariantAnimation(owner)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setDuration(max(0, int(duration)))
    anim.setEasingCurve(easing)
    anim.valueChanged.connect(setter)
    if finished is not None:
        anim.finished.connect(finished)
    store[key] = anim
    anim.start()
    return anim


def stop_animation(owner, key: str) -> None:
    """Stop the named animation on ``owner`` if one is running."""
    store = owner.__dict__.get("_nx_anims") or {}
    anim = store.get(key)
    if isinstance(anim, QVariantAnimation):
        try:
            anim.stop()
        except RuntimeError:
            pass
