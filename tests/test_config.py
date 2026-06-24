import pytest
from vesper.core.config import WindowConfig


def test_defaults():
    config = WindowConfig()
    assert config.title == "Vesper App"
    assert config.width == 800
    assert config.height == 600
    assert config.resizable is True
    assert config.fullscreen is False
    assert config.frontend == "frontend/index.html"


def test_custom_values():
    config = WindowConfig(title="My App", width=1280, height=720, frontend="dist/index.html")
    assert config.title == "My App"
    assert config.width == 1280
    assert config.height == 720
    assert config.frontend == "dist/index.html"


def test_title_stripped():
    config = WindowConfig(title="  My App  ")
    assert config.title == "My App"


def test_title_empty_raises():
    with pytest.raises(ValueError, match="title cannot be empty"):
        WindowConfig(title="")


def test_title_whitespace_raises():
    with pytest.raises(ValueError, match="title cannot be empty"):
        WindowConfig(title="   ")


def test_title_non_string_raises():
    with pytest.raises(TypeError, match="title must be a string"):
        WindowConfig(title=123)  # type: ignore


def test_width_zero_raises():
    with pytest.raises(ValueError, match="width must be greater than 0"):
        WindowConfig(width=0)


def test_width_negative_raises():
    with pytest.raises(ValueError, match="width must be greater than 0"):
        WindowConfig(width=-100)


def test_width_bool_raises():
    with pytest.raises(TypeError, match="width must be an integer"):
        WindowConfig(width=True)  # type: ignore


def test_height_zero_raises():
    with pytest.raises(ValueError, match="height must be greater than 0"):
        WindowConfig(height=0)


def test_height_non_integer_raises():
    with pytest.raises(TypeError, match="height must be an integer"):
        WindowConfig(height="600")  # type: ignore


def test_resizable_non_bool_raises():
    with pytest.raises(TypeError, match="resizable must be a boolean"):
        WindowConfig(resizable=1)  # type: ignore


def test_fullscreen_non_bool_raises():
    with pytest.raises(TypeError, match="fullscreen must be a boolean"):
        WindowConfig(fullscreen=0)  # type: ignore


def test_frontend_must_end_in_html():
    with pytest.raises(ValueError, match="frontend must point to an HTML file"):
        WindowConfig(frontend="index.js")


def test_frontend_empty_raises():
    with pytest.raises(ValueError):
        WindowConfig(frontend="")


def test_frontend_does_not_check_existence():
    config = WindowConfig(frontend="nonexistent/path/index.html")
    assert config.frontend == "nonexistent/path/index.html"