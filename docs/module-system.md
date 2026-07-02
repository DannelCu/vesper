# Module System & Dependency Injection

Vesper includes a NestJS-inspired module system for organizing larger applications. It provides dependency injection, feature modules, and controller-based command routing.

For small apps, none of this is required — `@app.command` on plain functions is enough. The module system becomes useful when your app has multiple logical domains (users, products, settings) or when services need to be shared across controllers.

---

## Core decorators

### @Injectable()

Marks a class as a DI provider (a service). Injectable classes can be resolved by the container and injected into controllers or other injectables.

```python
from vesper import Injectable

@Injectable()
class UserService:
    def __init__(self):
        self.users = {}

    def get(self, user_id: int):
        return self.users.get(user_id)

    def create(self, name: str) -> dict:
        uid = len(self.users) + 1
        self.users[uid] = {"id": uid, "name": name}
        return self.users[uid]
```

### @command

Marks a method on a controller as an IPC command. Supports the same three forms as `@app.command`:

```python
from vesper import command

class UsersController:
    @command                      # name: "users.get_user"
    def get_user(self, user_id: int): ...

    @command("create")            # name: "users.create"
    def create_user(self, name: str): ...

    @command(name="delete")       # name: "users.delete"
    def delete_user(self, user_id: int): ...
```

The full IPC command name is `"<prefix>.<method_name>"` (or `"<prefix>.<alias>"`).

### @Controller(prefix, guards=[])

Marks a class whose `@command` methods become IPC endpoints.

```python
from vesper import Controller, command

@Controller("users")
class UsersController:
    def __init__(self, user_service: UserService):
        self.svc = user_service

    @command
    def get_user(self, user_id: int) -> dict:
        return self.svc.get(user_id)

    @command
    def create_user(self, name: str) -> dict:
        return self.svc.create(name)
```

This registers `"users.get_user"` and `"users.create_user"` in the IPC registry.

`guards=[]` accepts a list of guard functions that apply to every command in this controller. They run before any method-level `@guard` decorators. See [Guards](guards.md).

### @Module(controllers, providers, imports)

Groups controllers, services, and sub-modules into a self-contained feature module.

```python
from vesper import Module

@Module(
    controllers=[UsersController],
    providers=[UserService],
    imports=[],
)
class UsersModule:
    pass
```

- `controllers` — list of `@Controller` classes whose commands are registered
- `providers` — list of `@Injectable` classes available for injection within this module
- `imports` — list of other `@Module` classes to recursively register first

---

## Dependency injection

The `Container` resolves providers by inspecting `__init__` type annotations. When a controller or injectable declares a constructor parameter with a type that matches a registered provider, the container injects the singleton instance automatically.

```python
@Injectable()
class EmailService:
    def send(self, to: str, subject: str): ...

@Injectable()
class UserService:
    def __init__(self, email: EmailService):   # ← injected
        self.email = email
```

**Resolution rules:**
- Parameters with a concrete `type` annotation are resolved from the container
- Primitive types (`str`, `int`, etc.) and unannotated parameters are skipped
- Each provider is a singleton within its module's container

---

## Wiring a module tree into the app

```python
from vesper import App

app = App(root_module=AppModule)
```

`App(root_module=...)` calls `app.register_module()` automatically. You can also call it manually:

```python
app.register_module(AppModule)
```

`register_module` recurses the module tree:
1. Recurses into `imports` first
2. Creates a `Container` for the module's `providers`
3. For each controller, resolves it through the container and registers every `@command` method

---

## Root module pattern

For multi-module apps, create a root module that imports all feature modules:

```python
# modules/app_module.py
from vesper import Module
from modules.users.users_module import UsersModule
from modules.products.products_module import ProductsModule

@Module(
    controllers=[],
    providers=[],
    imports=[UsersModule, ProductsModule],
)
class AppModule:
    pass
```

```python
# app.py
from vesper import App
from modules.app_module import AppModule

app = App(root_module=AppModule)

if __name__ == "__main__":
    app.run()
```

Use `vesper g module <name>` to scaffold module directories:

```bash
vesper g module users
vesper g module products
```

---

## Plugin DI integration

Plugins can register global providers available across all modules:

```python
from vesper import App
from vesper_db import DatabasePlugin, DbSession

app = App(
    plugins=[DatabasePlugin(url="sqlite:///app.db")],
    root_module=AppModule,
)
```

The plugin calls `Container.register_global(DbSession, session)` during registration. Any controller or service that declares `db: DbSession` in its `__init__` receives the session automatically.

```python
from vesper import Injectable
from vesper_db import DbSession

@Injectable()
class UserService:
    def __init__(self, db: DbSession):
        self.db = db   # scoped_session injected by DatabasePlugin
```

Plugins always register before modules — `App.__init__` runs plugins first so global providers are available when the module tree resolves.

---

## Scaffold with vesper generate

```bash
vesper g module users
```

Creates `modules/users/` with:

```
modules/users/
├── __init__.py
├── users_service.py
├── users_controller.py
└── users_module.py
```

On the first module, also creates `modules/app_module.py`. On subsequent modules, prints the import line to add manually.

---

## Full example

```python
# modules/users/users_service.py
from vesper import Injectable

@Injectable()
class UserService:
    def __init__(self):
        self._users: dict[int, dict] = {}
        self._next_id = 1

    def list(self) -> list[dict]:
        return list(self._users.values())

    def create(self, name: str) -> dict:
        uid = self._next_id
        self._next_id += 1
        self._users[uid] = {"id": uid, "name": name}
        return self._users[uid]
```

```python
# modules/users/users_controller.py
from vesper import Controller, command
from modules.users.users_service import UserService

@Controller("users")
class UsersController:
    def __init__(self, svc: UserService):
        self.svc = svc

    @command
    def list_users(self) -> list[dict]:
        return self.svc.list()

    @command
    def create_user(self, name: str) -> dict:
        return self.svc.create(name)
```

```python
# modules/users/users_module.py
from vesper import Module
from modules.users.users_service import UserService
from modules.users.users_controller import UsersController

@Module(controllers=[UsersController], providers=[UserService])
class UsersModule:
    pass
```

```js
// JS — call the registered commands
const users = await vesper.invoke("users.list_users")
const newUser = await vesper.invoke("users.create_user", { name: "Alice" })
```
