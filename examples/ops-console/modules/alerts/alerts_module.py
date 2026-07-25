from vesper import Module

from modules.alerts.settings_service import SettingsService
from modules.alerts.alerts_service import AlertsService
from modules.alerts.alerts_controller import AlertsController


@Module(controllers=[AlertsController], providers=[SettingsService, AlertsService])
class AlertsModule:
    pass
