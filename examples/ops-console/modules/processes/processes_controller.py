from vesper import Controller, command, guard

from modules.auth.guards import require_auth, require_admin
from modules.processes.processes_service import ProcessesService


@Controller("processes", guards=[require_auth])
class ProcessesController:
    def __init__(self, service: ProcessesService):
        self.service = service

    @command
    def available(self, token: str) -> bool:
        return self.service.available()

    @command
    def list(
        self,
        token: str,
        search: str = "",
        sort_by: str = "cpu_percent",
        sort_dir: str = "desc",
        page: int = 1,
        page_size: int = 25,
    ) -> dict:
        return self.service.list(
            search=search, sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size
        )

    @command
    @guard(require_admin)
    def terminate(self, token: str, pid: int) -> bool:
        """
        Admin only. This is the flagship guard demo: a viewer token fails
        require_admin with ForbiddenError before this method ever runs — see
        the README's guided tour and modules/auth/guards.py.
        """
        return self.service.terminate(pid)
