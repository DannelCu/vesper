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

    def __post_init__(self) -> None:
        self.title = self._validate_non_empty_string("title", self.title)
        self.width = self._validate_positive_integer("width", self.width)
        self.height = self._validate_positive_integer("height", self.height)
        self.resizable = self._validate_boolean("resizable", self.resizable)
        self.fullscreen = self._validate_boolean("fullscreen", self.fullscreen)
        self.minimized = self._validate_boolean("minimized", self.minimized)
        self.on_top = self._validate_boolean("on_top", self.on_top)
        self.frontend = self._validate_frontend(self.frontend)

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
