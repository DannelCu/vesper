from __future__ import annotations

import argparse
import re
from pathlib import Path


# ── Name helpers ──────────────────────────────────────────────────────────────


def _to_snake(name: str) -> str:
    """'UserOrders' or 'user-orders' → 'user_orders'"""
    name = name.replace("-", "_")
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    name = re.sub(r"[^a-z0-9_]", "_", name.lower())
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def _to_pascal(snake: str) -> str:
    """'user_orders' → 'UserOrders'"""
    return "".join(part.capitalize() for part in snake.split("_") if part)


# ── File content factories ────────────────────────────────────────────────────


def _service_content(pascal: str) -> str:
    return f"""\
from vesper import Injectable


@Injectable()
class {pascal}Service:
    pass
"""


def _controller_content(snake: str, pascal: str, with_service: bool = False) -> str:
    if with_service:
        return f"""\
from vesper import Controller, command
from .{snake}_service import {pascal}Service


@Controller("{snake}")
class {pascal}Controller:
    def __init__(self, svc: {pascal}Service):
        self.svc = svc
"""
    return f"""\
from vesper import Controller, command


@Controller("{snake}")
class {pascal}Controller:
    pass
"""


def _module_content(snake: str, pascal: str) -> str:
    return f"""\
from vesper import Module
from .{snake}_controller import {pascal}Controller
from .{snake}_service import {pascal}Service


@Module(
    controllers=[{pascal}Controller],
    providers=[{pascal}Service],
)
class {pascal}Module:
    pass
"""


def _init_content(snake: str, pascal: str) -> str:
    return f"""\
from .{snake}_module import {pascal}Module

__all__ = ["{pascal}Module"]
"""


def _app_module_content(snake: str, pascal: str) -> str:
    return f"""\
from vesper import Module
from .{snake}.{snake}_module import {pascal}Module


@Module(imports=[{pascal}Module])
class AppModule:
    pass
"""


# ── Generators ────────────────────────────────────────────────────────────────


def _write(path: Path, content: str) -> bool:
    """Write file; return False (and warn) if it already exists."""
    if path.exists():
        print(f"  skip  {path}  (already exists)")
        return False
    path.write_text(content, encoding="utf-8")
    print(f"  create  {path}")
    return True


def generate_module(name: str, project_dir: Path) -> None:
    snake = _to_snake(name)
    pascal = _to_pascal(snake)
    module_dir = project_dir / "modules" / snake

    module_dir.mkdir(parents=True, exist_ok=True)

    _write(module_dir / "__init__.py", _init_content(snake, pascal))
    _write(module_dir / f"{snake}_service.py", _service_content(pascal))
    _write(module_dir / f"{snake}_controller.py", _controller_content(snake, pascal, with_service=True))
    _write(module_dir / f"{snake}_module.py", _module_content(snake, pascal))

    app_module_path = project_dir / "modules" / "app_module.py"
    if not app_module_path.exists():
        _write(app_module_path, _app_module_content(snake, pascal))
        print(f"\nModule '{snake}' created at modules/{snake}/")
        print("\nTo use it in app.py:")
        print("  from modules.app_module import AppModule")
        print("  app = App(root_module=AppModule)")
    else:
        print(f"\nModule '{snake}' created at modules/{snake}/")
        print("\nAdd to modules/app_module.py:")
        print(f"  from .{snake}.{snake}_module import {pascal}Module")
        print(f"  # then add {pascal}Module to @Module(imports=[...])")


def generate_controller(name: str, project_dir: Path) -> None:
    snake = _to_snake(name)
    pascal = _to_pascal(snake)
    module_dir = project_dir / "modules" / snake

    module_dir.mkdir(parents=True, exist_ok=True)

    init = module_dir / "__init__.py"
    if not init.exists():
        init.write_text("", encoding="utf-8")
        print(f"  create  {init}")

    _write(module_dir / f"{snake}_controller.py", _controller_content(snake, pascal))

    print(f"\nController '{pascal}Controller' created at modules/{snake}/")


def generate_service(name: str, project_dir: Path) -> None:
    snake = _to_snake(name)
    pascal = _to_pascal(snake)
    module_dir = project_dir / "modules" / snake

    module_dir.mkdir(parents=True, exist_ok=True)

    init = module_dir / "__init__.py"
    if not init.exists():
        init.write_text("", encoding="utf-8")
        print(f"  create  {init}")

    _write(module_dir / f"{snake}_service.py", _service_content(pascal))

    print(f"\nService '{pascal}Service' created at modules/{snake}/")


# ── CLI ───────────────────────────────────────────────────────────────────────


_GENERATORS = {
    "module": generate_module,
    "controller": generate_controller,
    "service": generate_service,
}


def _add_generate_subparser(subparsers: argparse._SubParsersAction, name: str) -> None:
    p = subparsers.add_parser(name, help="Generate a module, controller, or service.")
    p.add_argument(
        "generate_type",
        choices=list(_GENERATORS),
        metavar="TYPE",
        help="What to generate: " + " | ".join(_GENERATORS),
    )
    p.add_argument("name", help="Name (e.g. users, user-orders, UserOrders)")


def add_generate_parser(subparsers: argparse._SubParsersAction) -> None:
    _add_generate_subparser(subparsers, "generate")
    _add_generate_subparser(subparsers, "g")


def handle_generate(args: argparse.Namespace) -> bool:
    if args.command not in ("generate", "g"):
        return False

    gen_fn = _GENERATORS[args.generate_type]
    gen_fn(args.name, Path.cwd())
    return True
