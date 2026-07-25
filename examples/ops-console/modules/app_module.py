from vesper import Module

from modules.auth.auth_module import AuthModule
from modules.metrics.metrics_module import MetricsModule
from modules.processes.processes_module import ProcessesModule
from modules.alerts.alerts_module import AlertsModule


@Module(imports=[AuthModule, MetricsModule, ProcessesModule, AlertsModule])
class AppModule:
    pass
