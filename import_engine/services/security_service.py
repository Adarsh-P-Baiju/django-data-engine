import pyclamd
from django.conf import settings

class VirusScanner:
    def __init__(self):
        host = getattr(settings, 'CLAMAV_HOST', 'clamav')
        port = int(getattr(settings, 'CLAMAV_PORT', 3310))
        self._scanner = None
        self.host = host
        self.port = port
        
    def _get_scanner(self):
        if not self._scanner:
            self._scanner = pyclamd.ClamdNetworkSocket(self.host, self.port)
        return self._scanner

    def scan_file(self, file_path: str) -> tuple[bool, str | None]:
        """
        Scans a file at absolute path (must be accessible to the clamav container).
        Returns (is_clean, virus_name_if_any)
        """
        try:
            scanner = self._get_scanner()
            result = scanner.scan_file(file_path)
            
            if result is None:
                return True, None
                
            virus_name = result.get(file_path, ('', 'Unknown Virus'))[1]
            return False, virus_name
            
        except pyclamd.ConnectionError as e:
            raise RuntimeError(f"Could not connect to ClamAV daemon: {e}")
