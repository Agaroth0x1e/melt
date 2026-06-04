import os
import json
import uuid
import re


class RuleManager:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self._path = config.resolve_path(os.path.join('config', 'rules.json'))
        self._rules = self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Failed to load rules: {e}")
        return []

    def _save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, 'w', encoding='utf-8') as f:
            json.dump(self._rules, f, indent=2)

    def add(self, match, action):
        rule = {
            'id': uuid.uuid4().hex[:8],
            'match': match,
            'action': action,
        }
        self._rules.append(rule)
        self._save()
        return rule['id']

    def remove(self, rule_id):
        before = len(self._rules)
        self._rules = [r for r in self._rules if r['id'] != rule_id]
        if len(self._rules) == before:
            return False
        self._save()
        return True

    def list(self):
        return list(self._rules)

    def match(self, info):
        for rule in self._rules:
            m = rule.get('match', {})
            channel = m.get('channel', '').lower()
            keyword = m.get('keyword', '').lower()
            url_pat = m.get('url_pattern', '')

            title = (info.get('title') or '').lower()
            uploader = (info.get('uploader') or info.get('channel') or info.get('playlist') or '').lower()
            url = (info.get('url') or '').lower()

            if channel and channel not in uploader:
                continue
            if keyword and keyword not in title:
                continue
            if url_pat and not re.search(url_pat, url, re.IGNORECASE):
                continue

            return rule.get('action', {})
        return None
