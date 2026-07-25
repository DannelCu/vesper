from vesper import Module

from modules.metrics.metrics_service import MetricsService
from modules.metrics.metrics_controller import MetricsController


@Module(controllers=[MetricsController], providers=[MetricsService])
class MetricsModule:
    pass
