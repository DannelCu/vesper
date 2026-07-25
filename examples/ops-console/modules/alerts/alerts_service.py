"""
Threshold evaluation over the metrics stream.

AlertsService depends on MetricsService (injected — the same globally-shared
instance MetricsController uses, see modules/metrics/metrics_service.py) and
on SettingsService (module-local, auto-built by AlertsModule's own
container). This is the DI edge the plan calls for: alerts consumes metrics,
not four independent singletons.
"""
from __future__ import annotations

import itertools
import time
from typing import Callable

from vesper import Injectable

from modules.alerts.settings_service import SettingsService
from modules.metrics.metrics_service import MetricsService

_METRICS = ("cpu_percent", "mem_percent")


@Injectable()
class AlertsService:
    def __init__(self, metrics: MetricsService, settings: SettingsService) -> None:
        self.metrics = metrics
        self.settings = settings

        self._alerts: list[dict] = []
        self._ids = itertools.count(1)
        # How long each metric has been continuously over threshold, or None.
        self._breach_since: dict[str, float | None] = {m: None for m in _METRICS}
        # The currently-open alert id for each metric, so a sustained breach
        # raises one alert rather than one per sample.
        self._open: dict[str, int | None] = {m: None for m in _METRICS}

        self._on_trigger: Callable[[dict], None] | None = None
        self._on_change: Callable[[int], None] | None = None

        metrics.on_sample(self._on_sample)

    def on_trigger(self, callback: Callable[[dict], None]) -> None:
        """Called once, with the new alert, when a threshold is first breached."""
        self._on_trigger = callback

    def on_change(self, callback: Callable[[int], None]) -> None:
        """Called with the unresolved count after any trigger or resolve — for the taskbar badge."""
        self._on_change = callback

    def _on_sample(self, sample: dict) -> None:
        thresholds = self.settings.get()
        duration = thresholds["duration_seconds"]
        values = {"cpu_percent": sample["cpu"], "mem_percent": sample["mem"]}

        for metric in _METRICS:
            value = values[metric]
            threshold = thresholds[metric]

            if value < threshold:
                self._breach_since[metric] = None
                continue

            if self._breach_since[metric] is None:
                self._breach_since[metric] = sample["ts"]
            elif (
                self._open[metric] is None
                and sample["ts"] - self._breach_since[metric] >= duration
            ):
                self._trigger(metric, value, threshold)

    def _trigger(self, metric: str, value: float, threshold: float) -> None:
        alert = {
            "id": next(self._ids),
            "metric": metric,
            "value": value,
            "threshold": threshold,
            "triggered_at": time.time(),
            "resolved": False,
            "resolved_at": None,
        }
        self._alerts.append(alert)
        self._open[metric] = alert["id"]

        if self._on_trigger is not None:
            try:
                self._on_trigger(alert)
            except Exception:
                pass
        self._notify_change()

    def _notify_change(self) -> None:
        if self._on_change is not None:
            try:
                self._on_change(self.unresolved_count())
            except Exception:
                pass

    def list(self) -> list[dict]:
        return list(reversed(self._alerts))

    def get(self, alert_id: int) -> dict | None:
        return next((a for a in self._alerts if a["id"] == alert_id), None)

    def unresolved_count(self) -> int:
        return sum(1 for a in self._alerts if not a["resolved"])

    def resolve(self, alert_id: int) -> dict:
        alert = self.get(alert_id)
        if alert is None:
            raise ValueError(f"No such alert: {alert_id}")

        alert["resolved"] = True
        alert["resolved_at"] = time.time()
        if self._open.get(alert["metric"]) == alert_id:
            self._open[alert["metric"]] = None

        self._notify_change()
        return alert
