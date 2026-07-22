from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class WindowConfig:
    """
    Configuration for the Vesper application window.
    """

    title: str = "Vesper App"
    width: int = 800
    height: int = 600
    resizable: bool = True
    fullscreen: bool = False
    minimized: bool = False
    on_top: bool = False
    frontend: str = "frontend/index.html"

    # Screen position. None means "let the backend place the window", which is the
    # default centring. Negative values are legitimate: a monitor arranged to the
    # left of or above the primary one has negative coordinates.
    x: int | None = None
    y: int | None = None

    # Chrome and compositing. easy_drag only matters when frameless is True: it
    # makes the whole window draggable, which a custom titlebar app turns off in
    # favour of declared drag regions. vibrancy is macOS-only; elsewhere PyWebView
    # ignores it. transparent depends on the compositor on Linux.
    frameless: bool = False
    easy_drag: bool = True
    transparent: bool = False
    vibrancy: bool = False

    # Minimum window size. None leaves the backend default; both must be set
    # together for a minimum to apply.
    min_width: int | None = None
    min_height: int | None = None

    def __post_init__(self) -> None:
        self.title = self._validate_non_empty_string("title", self.title)
        self.width = self._validate_positive_integer("width", self.width)
        self.height = self._validate_positive_integer("height", self.height)
        self.resizable = self._validate_boolean("resizable", self.resizable)
        self.fullscreen = self._validate_boolean("fullscreen", self.fullscreen)
        self.minimized = self._validate_boolean("minimized", self.minimized)
        self.on_top = self._validate_boolean("on_top", self.on_top)
        self.frontend = self._validate_frontend(self.frontend)
        self.x = self._validate_optional_integer("x", self.x)
        self.y = self._validate_optional_integer("y", self.y)
        self.frameless = self._validate_boolean("frameless", self.frameless)
        self.easy_drag = self._validate_boolean("easy_drag", self.easy_drag)
        self.transparent = self._validate_boolean("transparent", self.transparent)
        self.vibrancy = self._validate_boolean("vibrancy", self.vibrancy)
        self.min_width = self._validate_optional_positive_integer("min_width", self.min_width)
        self.min_height = self._validate_optional_positive_integer("min_height", self.min_height)
        if (self.min_width is None) != (self.min_height is None):
            raise ValueError("min_width and min_height must be set together.")

    @staticmethod
    def _validate_optional_integer(field_name: str, value: int | None) -> int | None:
        if value is None:
            return None

        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{field_name} must be an integer or None.")

        return value

    @classmethod
    def _validate_optional_positive_integer(cls, field_name: str, value: int | None) -> int | None:
        if value is None:
            return None

        return cls._validate_positive_integer(field_name, value)

    @staticmethod
    def _validate_non_empty_string(field_name: str, value: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field_name} must be a string.")

        normalized = value.strip()

        if not normalized:
            raise ValueError(f"{field_name} cannot be empty.")

        return normalized

    @staticmethod
    def _validate_positive_integer(field_name: str, value: int) -> int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{field_name} must be an integer.")

        if value <= 0:
            raise ValueError(f"{field_name} must be greater than 0.")

        return value

    @staticmethod
    def _validate_boolean(field_name: str, value: bool) -> bool:
        if not isinstance(value, bool):
            raise TypeError(f"{field_name} must be a boolean.")

        return value

    @classmethod
    def _validate_frontend(cls, value: str) -> str:
        frontend = cls._validate_non_empty_string("frontend", value)

        if not frontend.lower().endswith(".html"):
            raise ValueError("frontend must point to an HTML file.")

        return frontend
