"""
Alert thresholds — a tiny settings store in the spirit of
docs/recipes/user-preferences.md, kept in memory rather than persisted with
vesper-store: this app's five pluggable pieces (keychain, sysinfo, db,
notify, theme) don't include vesper-store, and thresholds resetting to their
defaults on restart is an honest, clearly-documented limitation rather than a
missing feature — see the README.
"""
from __future__ import annotations

from vesper import Injectable

DEFAULT_THRESHOLDS = {
    "cpu_percent": 80.0,
    "mem_percent": 85.0,
    "duration_seconds": 5.0,
}


@Injectable()
class SettingsService:
    def __init__(self) -> None:
        self.thresholds = dict(DEFAULT_THRESHOLDS)

    def get(self) -> dict:
        return dict(self.thresholds)

    def update(
        self,
        *,
        cpu_percent: float | None = None,
        mem_percent: float | None = None,
        duration_seconds: float | None = None,
    ) -> dict:
        if cpu_percent is not None:
            self.thresholds["cpu_percent"] = max(1.0, min(100.0, cpu_percent))
        if mem_percent is not None:
            self.thresholds["mem_percent"] = max(1.0, min(100.0, mem_percent))
        if duration_seconds is not None:
            self.thresholds["duration_seconds"] = max(0.0, duration_seconds)
        return self.get()
