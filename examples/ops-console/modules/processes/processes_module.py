from vesper import Module

from modules.processes.processes_service import ProcessesService
from modules.processes.processes_controller import ProcessesController


@Module(controllers=[ProcessesController], providers=[ProcessesService])
class ProcessesModule:
    pass
