"""Pygame without its start-up noise.

Pygame 2.6 prints a "Hello from the pygame community" banner and, on
setuptools 81 or later, a warning that pkg_resources is going away. Neither
matters to ZAE: pygame already falls back cleanly when pkg_resources is gone
(it only uses it to find bundled resources, which ZAE never asks for), so a
future setuptools can't break her audio. This hides both messages from the
console windows. Import pygame from here: from core.voice_output.quiet_pygame import pygame
"""
from __future__ import annotations

import os
import warnings

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message=r"pkg_resources is deprecated", category=UserWarning)
    import pygame  # noqa: E402

__all__ = ["pygame"]
