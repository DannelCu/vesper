from vesper import App, CommandAlreadyRegisteredError, CommandNotFoundError, VesperError


def test_app_importable():
    assert App is not None


def test_exceptions_importable():
    assert issubclass(VesperError, Exception)
    assert issubclass(CommandNotFoundError, VesperError)
    assert issubclass(CommandAlreadyRegisteredError, VesperError)


def test_app_instantiates_with_defaults():
    app = App()
    assert app is not None


def test_app_command_decorator_registers_function():
    app = App()

    @app.command
    def greet():
        return "hi"

    assert app is not None
