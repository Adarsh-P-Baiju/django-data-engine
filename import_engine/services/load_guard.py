import time
import logging

logger = logging.getLogger(__name__)


class LoadGuardService:
    """Adaptive Backpressure System. Monitors metrics and throttles processing."""

    THRESHOLD_CPU = 85.0
    THRESHOLD_RAM = 85.0

    @classmethod
    def get_system_load(cls) -> dict:
        """Collects current CPU and RAM utilization metrics."""
        try:
            import psutil

            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            return {"cpu": cpu, "ram": ram}
        except ImportError:
            # Fallback for environments without psutil
            return {"cpu": 0.0, "ram": 0.0}

    @classmethod
    def throttle(cls, factor: float = 0.1):
        """
        Injects a dynamic wait period if system load exceeds safe thresholds.
        Usage: call this at the end of every row or chunk processing loop.
        """
        metrics = cls.get_system_load()

        if metrics["cpu"] > cls.THRESHOLD_CPU or metrics["ram"] > cls.THRESHOLD_RAM:
            wait_time = factor * (max(metrics["cpu"], metrics["ram"]) / 100.0)
            logger.warning(
                f"LoadGuard: System Saturated (CPU: {metrics['cpu']}%, RAM: {metrics['ram']}%). Throttling for {round(wait_time, 3)}s"
            )
            time.sleep(wait_time)
            return True
        return False
