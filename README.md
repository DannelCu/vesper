# Vesper Architecture

## What is Vesper?

Vesper is an open-source desktop application framework for Python developers.

Its goal is to make it possible to build modern desktop applications using:

* Python for backend logic
* Web technologies for the user interface
* Native system WebViews for rendering

Vesper is inspired by the ideas pioneered by Tauri, but it is designed around a Python-first developer experience.

The project does not aim to replace Tauri, PyWebView, or existing desktop frameworks. Instead, it aims to provide a modern, lightweight, and developer-friendly layer on top of existing technologies.

---

# Why Vesper Exists

Python is one of the most popular programming languages in the world, but its desktop application ecosystem has several limitations.

Current options often require developers to:

* Learn a completely different UI framework
* Use outdated GUI toolkits
* Accept heavyweight solutions
* Build large amounts of boilerplate code

Meanwhile, modern web technologies have become the preferred way to create rich user interfaces.

Vesper aims to bridge that gap.

The vision is simple:

> Build desktop applications with Python and modern web technologies without forcing developers to learn Rust, C++, or a completely different UI framework.

---

# Core Principles

## 1. Python First

Python is the primary backend language.

The backend should never depend on Node.js or another runtime to execute application logic.

```python
from vesper import App

app = App()
```

---

## 2. Frontend Agnostic

Vesper should work with any frontend framework.

Examples:

* React
* Vue
* Svelte
* Solid
* Vanilla HTML/CSS/JavaScript

The framework should never force a specific frontend technology.

---

## 3. Lightweight Core

The core of Vesper should remain small and focused.

Only essential functionality belongs in the core:

* Application lifecycle
* Command registration
* IPC communication
* Window management

Everything else should be optional.

---

## 4. Explicit APIs

Nothing should be exposed automatically.

Developers must explicitly expose backend functionality.

Example:

```python
@app.command
def greet(name):
    return f"Hello {name}"
```

Only registered commands can be called from the frontend.

---

## 5. Secure by Default

Security is a fundamental design principle.

Frontend code should never gain unrestricted access to Python execution.

Instead, communication must happen through a controlled command system.

Allowed:

```javascript
await invoke("greet", {
  name: "John"
})
```

Not allowed:

```javascript
window.python.execute(...)
```

---

## 6. Message-Based Architecture

Communication between frontend and backend should be message-based.

All data crossing the frontend/backend boundary must be serializable.

Supported types:

* string
* integer
* float
* boolean
* list
* dictionary
* JSON-compatible structures

Unsupported types:

* database connections
* sockets
* threads
* file handles
* arbitrary Python objects

This philosophy is heavily inspired by Tauri's IPC model.

---

# Current Architecture

```text
Frontend
    │
    ▼
 invoke()
    │
    ▼
 IPC Layer
    │
    ▼
 Command Registry
    │
    ▼
 Python Commands
```

The frontend sends a message.

The IPC layer validates and routes the message.

The command registry locates the target command.

The command is executed in Python.

The result is returned back to the frontend.

---

# Project Structure

Current Milestone 1 structure:

```text
vesper/
│
├── __init__.py
│
└── core/
    ├── __init__.py
    ├── app.py
    ├── registry.py
    ├── ipc.py
    └── window.py
```

---

# File Responsibilities

## vesper/**init**.py

Public API entry point.

Responsibilities:

* Expose public classes
* Hide internal implementation details
* Provide a clean developer experience

Example:

```python
from vesper import App
```

---

## vesper/core/**init**.py

Internal package entry point.

Responsibilities:

* Export internal core components
* Organize core package imports
* Define internal package boundaries

---

## vesper/core/app.py

Application lifecycle manager.

Responsibilities:

* Create the application instance
* Initialize internal services
* Register commands
* Start the application

Future responsibilities may include:

* Plugin loading
* Configuration management
* Event management

---

## vesper/core/registry.py

Command registration system.

Responsibilities:

* Store registered commands
* Retrieve commands by name
* Validate command existence

Example:

```python
@app.command
def greet(name):
    return f"Hello {name}"
```

Internally:

```python
{
    "greet": greet
}
```

---

## vesper/core/ipc.py

Inter-Process Communication layer.

Responsibilities:

* Receive frontend messages
* Validate requests
* Resolve commands
* Execute commands
* Return responses
* Handle errors

This file represents the communication bridge between JavaScript and Python.

It is one of the most important components in the framework.

---

## vesper/core/window.py

Window abstraction layer.

Responsibilities:

* Create application windows
* Load frontend content
* Manage window lifecycle

Initially this module will be implemented using PyWebView.

However, the rest of the framework should not depend directly on PyWebView.

The goal is to keep the implementation abstract and replaceable.

---

# First Milestone

Milestone 1 focuses only on the foundation.

Goals:

* App class
* Command registry
* Command decorator
* Basic architecture

Not included:

* Plugins
* Packaging
* Auto-updates
* Filesystem APIs
* Dialog APIs
* Event system

The objective is to build a small, understandable, and stable foundation before adding more advanced features.

---

# Long-Term Vision

Vesper aims to become a modern desktop framework that gives Python developers an experience similar to what Tauri provides for Rust developers.

Future versions may include:

* CLI tools
* Frontend templates
* Plugin ecosystem
* Native APIs
* Packaging tools
* Event system
* Developer tooling

However, all future development must respect the original principles:

* Python First
* Frontend Agnostic
* Lightweight Core
* Explicit APIs
* Secure by Default
* Message-Based Architecture
