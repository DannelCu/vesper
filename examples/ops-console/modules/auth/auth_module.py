from vesper import Module

from modules.auth.auth_service import SessionService
from modules.auth.auth_controller import AuthController


@Module(controllers=[AuthController], providers=[SessionService])
class AuthModule:
    pass
