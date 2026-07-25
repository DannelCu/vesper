from vesper import Controller, command

from modules.auth.guards import require_auth
from modules.metrics.metrics_service import MetricsService


@Controller("metrics", guards=[require_auth])
class MetricsController:
    """
    Both roles can read metrics — this console has no write actions here,
    only alerts.set_thresholds (admin-only) reacts to what these expose.
    """

    def __init__(self, metrics: MetricsService):
        self.metrics = metrics

    @command
    def snapshot(self, token: str) -> dict:
        return self.metrics.snapshot()

    @command
    def history(self, token: str, limit: int = 120) -> list:
        return self.metrics.history(limit)

    @command
    def subscribe(self, token: str, interval: float = 2.0) -> bool:
        self.metrics.subscribe(interval=interval)
        return True

    @command
    def unsubscribe(self, token: str) -> bool:
        return self.metrics.unsubscribe()

    @command
    def source(self, token: str) -> dict:
        """
        Tells the dashboard whether it is looking at real or synthetic data —
        the honest banner the plan requires without the plugin installed.
        """
        return {"source": self.metrics.source}
