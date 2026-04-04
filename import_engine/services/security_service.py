import logging
import pyclamd
from typing import Dict, Any, Tuple, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class VirusScanner:
    """
    Advanced VirusScanner with connection lifecycle management.
    """

    def __init__(self):
        self.host = getattr(settings, "CLAMAV_HOST", "clamav")
        self.port = int(getattr(settings, "CLAMAV_PORT", 3310))
        self._scanner: Optional[pyclamd.ClamdNetworkSocket] = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _get_scanner(self) -> pyclamd.ClamdNetworkSocket:
        if not self._scanner:
            try:
                self._scanner = pyclamd.ClamdNetworkSocket(self.host, self.port)
            except pyclamd.ConnectionError as e:
                raise RuntimeError(f"Could not connect to ClamAV daemon: {e}")
        return self._scanner

    def scan_file(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Scans a file and returns (is_clean, virus_name).
        """
        scanner = self._get_scanner()
        try:
            result = scanner.scan_file(file_path)
            if result is None:
                return True, None

            virus_name = result.get(file_path, ("", "Unknown Virus"))[1]
            return False, virus_name
        except Exception as e:
            logger.error(f"VirusScanner Error: {e}")
            raise

    def close(self):
        """Explicitly close the network socket."""
        if self._scanner:


            self._scanner = None


def mask_pii(row_dict: Dict[str, Any], config: Any) -> Dict[str, Any]:
    """
    Advanced PII masking based on model configuration.
    Centralizes all masking logic to ensure consistency across logs and metrics.
    """
    safe_data = dict(row_dict)
    for field_name, field_cfg in config.fields.items():
        if isinstance(field_cfg, dict) and field_cfg.get("pii"):
            label = field_cfg.get("label", field_name)

            if label in safe_data:
                safe_data[label] = "*** MASKED ***"
            if field_name in safe_data:
                safe_data[field_name] = "*** MASKED ***"
    return safe_data
