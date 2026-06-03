import os
from datetime import datetime

class Logger:
    def __init__(self, log_path):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def _write(self, level, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")

    def info(self, message):
        self._write('INFO', message)

    def warn(self, message):
        self._write('WARN', message)

    def warning(self, message):
        self._write('WARN', message)

    def error(self, message):
        self._write('ERROR', message)
