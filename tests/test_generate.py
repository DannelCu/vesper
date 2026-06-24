import pytest
from pathlib import Path

from vesper.commands.generate import (
    _to_snake,
    _to_pascal,
    generate_controller,
    generate_module,
    generate_service,
)


# ── Name helpers ──────────────────────────────────────────────────────────────


def test_to_snake_lowercase():
    assert _to_snake("users") == "users"


def test_to_snake_hyphen():
    assert _to_snake("user-orders") == "user_orders"


def test_to_snake_camel():
    assert _to_snake("UserOrders") == "user_orders"


def test_to_snake_pascal_multiword():
    assert _to_snake("ProductCategory") == "product_category"


def test_to_pascal_simple():
    assert _to_pascal("users") == "Users"


def test_to_pascal_multiword():
    assert _to_pascal("user_orders") == "UserOrders"


# ── generate_module ───────────────────────────────────────────────────────────


def test_generate_module_creates_all_files(tmp_path):
    generate_module("users", tmp_path)
    base = tmp_path / "modules" / "users"
    assert (base / "__init__.py").exists()
    assert (base / "users_service.py").exists()
    assert (base / "users_controller.py").exists()
    assert (base / "users_module.py").exists()


def test_generate_module_service_content(tmp_path):
    generate_module("users", tmp_path)
    content = (tmp_path / "modules" / "users" / "users_service.py").read_text()
    assert "@Injectable()" in content
    assert "class UsersService:" in content


def test_generate_module_controller_content(tmp_path):
    generate_module("users", tmp_path)
    content = (tmp_path / "modules" / "users" / "users_controller.py").read_text()
    assert '@Controller("users")' in content
    assert "class UsersController:" in content
    assert "UsersService" in content


def test_generate_module_module_content(tmp_path):
    generate_module("users", tmp_path)
    content = (tmp_path / "modules" / "users" / "users_module.py").read_text()
    assert "@Module(" in content
    assert "UsersController" in content
    assert "UsersService" in content
    assert "class UsersModule:" in content


def test_generate_module_init_content(tmp_path):
    generate_module("users", tmp_path)
    content = (tmp_path / "modules" / "users" / "__init__.py").read_text()
    assert "UsersModule" in content


def test_generate_module_normalizes_hyphen_name(tmp_path):
    generate_module("user-orders", tmp_path)
    base = tmp_path / "modules" / "user_orders"
    assert base.is_dir()
    assert (base / "user_orders_module.py").exists()
    content = (base / "user_orders_controller.py").read_text()
    assert "class UserOrdersController:" in content


def test_generate_module_normalizes_pascal_name(tmp_path):
    generate_module("ProductCategory", tmp_path)
    base = tmp_path / "modules" / "product_category"
    assert (base / "product_category_module.py").exists()
    content = (base / "product_category_module.py").read_text()
    assert "class ProductCategoryModule:" in content


def test_generate_module_skips_existing_files(tmp_path):
    generate_module("users", tmp_path)
    # Modify the service file
    svc = tmp_path / "modules" / "users" / "users_service.py"
    svc.write_text("# custom content", encoding="utf-8")
    # Run again — should not overwrite
    generate_module("users", tmp_path)
    assert svc.read_text() == "# custom content"


# ── generate_controller ───────────────────────────────────────────────────────


def test_generate_controller_creates_controller_only(tmp_path):
    generate_controller("orders", tmp_path)
    base = tmp_path / "modules" / "orders"
    assert (base / "orders_controller.py").exists()
    assert not (base / "orders_service.py").exists()
    assert not (base / "orders_module.py").exists()


def test_generate_controller_content(tmp_path):
    generate_controller("orders", tmp_path)
    content = (tmp_path / "modules" / "orders" / "orders_controller.py").read_text()
    assert '@Controller("orders")' in content
    assert "class OrdersController:" in content


def test_generate_controller_no_service_import(tmp_path):
    generate_controller("orders", tmp_path)
    content = (tmp_path / "modules" / "orders" / "orders_controller.py").read_text()
    assert "OrdersService" not in content


def test_generate_controller_creates_empty_init(tmp_path):
    generate_controller("orders", tmp_path)
    assert (tmp_path / "modules" / "orders" / "__init__.py").exists()


def test_generate_controller_skips_existing_file(tmp_path):
    generate_controller("orders", tmp_path)
    ctrl = tmp_path / "modules" / "orders" / "orders_controller.py"
    ctrl.write_text("# custom", encoding="utf-8")
    generate_controller("orders", tmp_path)
    assert ctrl.read_text() == "# custom"


# ── generate_service ──────────────────────────────────────────────────────────


def test_generate_service_creates_service_only(tmp_path):
    generate_service("payment", tmp_path)
    base = tmp_path / "modules" / "payment"
    assert (base / "payment_service.py").exists()
    assert not (base / "payment_controller.py").exists()
    assert not (base / "payment_module.py").exists()


def test_generate_service_content(tmp_path):
    generate_service("payment", tmp_path)
    content = (tmp_path / "modules" / "payment" / "payment_service.py").read_text()
    assert "@Injectable()" in content
    assert "class PaymentService:" in content


def test_generate_service_skips_existing_file(tmp_path):
    generate_service("payment", tmp_path)
    svc = tmp_path / "modules" / "payment" / "payment_service.py"
    svc.write_text("# custom", encoding="utf-8")
    generate_service("payment", tmp_path)
    assert svc.read_text() == "# custom"


# ── Generated files are valid Vesper modules ─────────────────────────────────


def test_generated_module_importable_and_registerable(tmp_path, monkeypatch):
    """Files generated by 'vesper generate module' must actually work at runtime."""
    generate_module("greet", tmp_path)

    # Make tmp_path importable
    monkeypatch.syspath_prepend(str(tmp_path))

    from modules.greet.greet_module import GreetModule  # type: ignore[import]

    from vesper import App
    app = App()
    app.register_module(GreetModule)
    # Module registered without errors — scaffold is valid
