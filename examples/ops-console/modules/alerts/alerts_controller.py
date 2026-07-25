from __future__ import annotations

from vesper import Controller, command, guard

from modules.auth.guards import require_auth, require_admin
from modules.alerts.alerts_service import AlertsService
from modules.alerts.settings_service import SettingsService


@Controller("alerts", guards=[require_auth])
class AlertsController:
    def __init__(self, alerts: AlertsService, settings: SettingsService):
        self.alerts = alerts
        self.settings = settings

    @command
    def list(self, token: str) -> list:
        return self.alerts.list()

    @command
    def unresolved_count(self, token: str) -> int:
        return self.alerts.unresolved_count()

    @command
    def resolve(self, token: str, alert_id: int) -> dict:
        return self.alerts.resolve(alert_id)

    @command
    def get_thresholds(self, token: str) -> dict:
        return self.settings.get()

    @command
    @guard(require_admin)
    def set_thresholds(
        self,
        token: str,
        cpu_percent: float | None = None,
        mem_percent: float | None = None,
        duration_seconds: float | None = None,
    ) -> dict:
        """
        Admin only — a viewer sees the thresholds (get_thresholds) but
        cannot change them, the second guard demonstration the plan asks for.
        """
        return self.settings.update(
            cpu_percent=cpu_percent,
            mem_percent=mem_percent,
            duration_seconds=duration_seconds,
        )
