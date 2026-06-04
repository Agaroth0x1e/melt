import os
import subprocess


def _git(cmd, git_dir, work_tree):
    full = ['git', f'--git-dir={git_dir}', f'--work-tree={work_tree}'] + cmd
    try:
        r = subprocess.run(full, capture_output=True, text=True, timeout=30)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return -1, '', 'git not found'
    except subprocess.TimeoutExpired:
        return -1, '', 'git timed out'


_TRACKED = [
    'config/config.json',
    'config/rules.json',
    'config/schedule.json',
    'config/profiles/',
    'logs/stats.json',
    'logs/playlist_snapshots/',
]


class SyncManager:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.work_tree = config.working_dir
        self.git_dir = config.resolve_path(os.path.join('config', 'sync', '.git'))

    def _run(self, cmd):
        return _git(cmd, self.git_dir, self.work_tree)

    def init(self, remote_url=''):
        os.makedirs(os.path.dirname(self.git_dir), exist_ok=True)
        rc, out, err = _git(['init', '-b', 'main'], self.git_dir, self.work_tree)
        if rc != 0:
            return f"Init failed: {err}"
        _git(['config', 'user.name', 'MelT Sync'], self.git_dir, self.work_tree)
        _git(['config', 'user.email', 'sync@melt.local'], self.git_dir, self.work_tree)
        ig = ['# MelT sync tracked files']
        for p in _TRACKED:
            ig.append(p.replace('/', os.sep))
        ig_path = os.path.join(os.path.dirname(self.git_dir), '.gitignore')
        os.makedirs(os.path.dirname(ig_path), exist_ok=True)
        with open(ig_path, 'w') as f:
            f.write('\n'.join(ig) + '\n')
        rc, out, err = self._run(['add', '-A'])
        if rc != 0:
            return f"Add failed: {err}"
        rc, out, err = self._run(['commit', '-m', 'MelT sync init'])
        if rc != 0 and 'nothing to commit' not in (out + err):
            return f"Commit failed: {err}"
        if remote_url:
            rc, out, err = self._run(['remote', 'add', 'origin', remote_url])
            if rc != 0:
                return f"Remote add failed: {err}"
            rc, out, err = self._run(['push', '-u', 'origin', 'main'])
            if rc != 0:
                return f"Push failed: {err}"
        return "Sync initialized"

    def push(self, message=''):
        rc, out, err = self._run(['add', '-A'])
        if rc != 0:
            return f"Add failed: {err}"
        msg = message or f"MelT sync {__import__('datetime').datetime.now().isoformat()[:19]}"
        rc, out, err = self._run(['commit', '-m', msg])
        if rc != 0:
            if 'nothing to commit' in (out + err):
                return "Nothing to sync"
            return f"Commit failed: {err}"
        rc, out, err = self._run(['push'])
        if rc != 0:
            return f"Push failed: {err}"
        return "Synced successfully"

    def pull(self):
        rc, out, err = self._run(['stash'])
        rc2, out2, err2 = self._run(['pull', '--rebase'])
        if rc2 != 0:
            self._run(['stash', 'pop'])
            return f"Pull failed: {err2}"
        self._run(['stash', 'drop'])
        return "Pulled successfully"

    def status(self):
        if not os.path.isdir(self.git_dir):
            return "Not a sync repository. Use 'melt sync init' first."
        rc, out, err = self._run(['status'])
        return out

    def remote_status(self):
        rc, out, err = self._run(['remote', '-v'])
        if rc != 0:
            return "No remote configured"
        lines = out.split('\n')
        rc2, out2, err2 = self._run(['log', '--oneline', '-3'])
        recent = f"\nRecent commits:\n{out2}" if out2 else ''
        return '\n'.join(lines) + recent
