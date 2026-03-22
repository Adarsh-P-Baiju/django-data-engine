import logging
import json


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "level": record.levelname,
            "module": record.module,
            "msg": record.msg if isinstance(record.msg, dict) else str(record.msg),
        }
        return json.dumps(log_data)
