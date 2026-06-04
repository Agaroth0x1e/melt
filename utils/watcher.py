import os
import re
import sys
import time

_URL_RE = re.compile(r'https?://[^\s<>"\'|]+', re.IGNORECASE)


def _extract_urls(content):
    return _URL_RE.findall(content)


def _read_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(path, 'r', encoding='latin-1') as f:
                return f.read()
        except Exception:
            return ''


def _check_abort():
    if sys.platform == 'win32':
        import msvcrt
        if msvcrt.kbhit():
            key = msvcrt.getch().decode('utf-8', errors='replace').lower()
            if key in ('t', '\x14'):
                return True
    else:
        import select
        if select.select([sys.stdin], [], [], 0)[0]:
            key = sys.stdin.read(1).lower()
            if key in ('t', '\x14'):
                return True
    return False


class FolderWatcher:
    def __init__(self, config, logger, mother_script_factory):
        self.config = config
        self.logger = logger
        self.mother_script_factory = mother_script_factory
        watch_cfg = config.get('watch_folder', {})
        self._enabled = watch_cfg.get('enabled', False)
        self._path = config.resolve_path(watch_cfg.get('path', 'watch'))
        self._interval = watch_cfg.get('interval_seconds', 60)
        self._auto_delete = watch_cfg.get('auto_delete', True)
        wf = watch_cfg.get('default_format', config.get('general', {}).get('default_format', 'video'))
        wd = watch_cfg.get('default_dest', config.get('general', {}).get('downloads_dir', 'downloads'))
        self._watch_fmt = wf
        self._watch_dest = wd

    def run(self):
        os.makedirs(self._path, exist_ok=True)
        self.logger.info(f"Watch folder started: {self._path}")
        print(f"[Watch] Watching: {self._path} (Ctrl+T to stop)")
        while True:
            try:
                self._scan()
            except Exception as e:
                self.logger.error(f"Watch scan error: {e}")
            for _ in range(self._interval * 2):
                if _check_abort():
                    print("[Watch] Stopped")
                    self.logger.info("Watch folder stopped by user")
                    return
                time.sleep(0.5)

    def _scan(self):
        if not os.path.isdir(self._path):
            return
        for fname in os.listdir(self._path):
            fpath = os.path.join(self._path, fname)
            if not os.path.isfile(fpath):
                continue
            content = _read_file(fpath)
            urls = _extract_urls(content)
            if urls:
                self.logger.info(f"Watch folder: found {len(urls)} URL(s) in {fname}")
                print(f"\n[Watch] Found {len(urls)} URL(s) in {fname}")
                batch_url = ' '.join(urls)
                try:
                    ms = self.mother_script_factory()
                    ms.batch_download(batch_url, self._watch_fmt, self._watch_dest)
                except Exception as e:
                    self.logger.error(f"Watch download failed for {fname}: {e}")
                    print(f"[Watch] Download failed for {fname}: {e}")
                if self._auto_delete:
                    try:
                        os.remove(fpath)
                        print(f"[Watch] Deleted {fname}")
                    except Exception as e:
                        self.logger.error(f"Failed to delete {fname}: {e}")
            else:
                self.logger.debug(f"No URLs in {fname}")
