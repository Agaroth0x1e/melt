import os
import json
import time
import uuid
from datetime import datetime, timedelta


class Scheduler:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self._path = config.resolve_path(os.path.join('config', 'schedule.json'))

    def _load(self):
        if not os.path.exists(self._path):
            return {'jobs': []}
        with open(self._path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save(self, data):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def add(self, url, interval_hours=0, at_time='', fmt='video', dest='downloads'):
        data = self._load()
        now = datetime.now()
        if interval_hours > 0:
            next_run = (now + timedelta(hours=interval_hours)).isoformat()
        elif at_time:
            parts = at_time.split(':')
            h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
            candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if candidate <= now:
                candidate += timedelta(days=1)
            next_run = candidate.isoformat()
            interval_hours = 24
        else:
            next_run = now.isoformat()
            interval_hours = 0

        job = {
            'id': uuid.uuid4().hex[:8],
            'url': url,
            'interval_hours': interval_hours,
            'next_run': next_run,
            'last_run': None,
            'fmt': fmt,
            'dest': dest,
            'enabled': True,
        }
        data['jobs'].append(job)
        self._save(data)
        return job['id']

    def remove(self, job_id):
        data = self._load()
        before = len(data['jobs'])
        data['jobs'] = [j for j in data['jobs'] if j['id'] != job_id]
        if len(data['jobs']) == before:
            return False
        self._save(data)
        return True

    def list(self):
        return self._load()['jobs']

    def due_jobs(self):
        data = self._load()
        now = datetime.now()
        due = []
        for job in data['jobs']:
            if not job.get('enabled', True):
                continue
            next_dt = datetime.fromisoformat(job['next_run'])
            if next_dt <= now:
                due.append(job)
        return due

    def mark_run(self, job_id):
        data = self._load()
        now = datetime.now().isoformat()
        for job in data['jobs']:
            if job['id'] == job_id:
                job['last_run'] = now
                if job['interval_hours'] > 0:
                    next_dt = datetime.now() + timedelta(hours=job['interval_hours'])
                    job['next_run'] = next_dt.isoformat()
                else:
                    job['enabled'] = False
                    job['next_run'] = None
                break
        self._save(data)

    def run_due(self, mother_script_factory):
        due = self.due_jobs()
        if not due:
            return False
        self.logger.info(f"Scheduler: {len(due)} job(s) due")
        for job in due:
            url = job['url']
            fmt = job.get('fmt', 'video')
            dest = job.get('dest', 'downloads')
            self.logger.info(f"Running scheduled job {job['id']}: {url}")
            ms = mother_script_factory()
            ms.batch_download(url, fmt, dest)
            self.mark_run(job['id'])
        return True
