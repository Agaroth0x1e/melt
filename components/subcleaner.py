import os
import re


class SubCleaner:
    def __init__(self, logger):
        self.logger = logger

    def clean_subtitle_file(self, srt_path):
        if not srt_path or not os.path.exists(srt_path):
            return srt_path

        self.logger.info(f"Cleaning subtitle: {srt_path}")

        is_vtt = srt_path.endswith('.vtt')

        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        entries = self._parse_entries(content, is_vtt)
        cleaned = self._remove_rollup(entries)

        base, ext = os.path.splitext(srt_path)
        out_path = f"{base}.clean.srt"

        self._write_srt(cleaned, out_path)
        return out_path

    def _parse_entries(self, content, is_vtt):
        entries = []
        if is_vtt:
            lines = content.split('\n')
            i = 0
            while i < len(lines):
                if lines[i].strip() == '':
                    i += 1
                    continue
                if lines[i].startswith('WEBVTT') or lines[i].startswith('Kind:') or lines[i].startswith('Language:'):
                    i += 1
                    continue
                if '-->' in lines[i]:
                    time_line = lines[i].strip()
                    time_line = re.sub(r'\.(\d{3})', r',\1', time_line)
                    i += 1
                    text_lines = []
                    while i < len(lines) and lines[i].strip() != '':
                        text_lines.append(lines[i].strip())
                        i += 1
                    if text_lines:
                        entries.append({'time': time_line, 'text': '\n'.join(text_lines)})
                else:
                    i += 1
        else:
            blocks = re.split(r'\n\s*\n', content.strip())
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 2 and '-->' in lines[1]:
                    time_line = lines[1].strip()
                    text_lines = [ln for ln in lines[2:] if ln.strip()]
                    if text_lines:
                        entries.append({'time': time_line, 'text': '\n'.join(text_lines)})
                elif len(lines) >= 1 and '-->' in lines[0]:
                    time_line = lines[0].strip()
                    text_lines = [ln for ln in lines[1:] if ln.strip()]
                    if text_lines:
                        entries.append({'time': time_line, 'text': '\n'.join(text_lines)})
        return entries

    def _remove_rollup(self, entries):
        cleaned = []
        prev_lines = set()

        for entry in entries:
            current_lines = [ln.strip() for ln in entry['text'].split('\n') if ln.strip()]

            new_lines = [ln for ln in current_lines if ln not in prev_lines]

            if new_lines:
                cleaned.append({
                    'time': entry['time'],
                    'text': '\n'.join(new_lines),
                    'original_text': entry['text'],
                })
                prev_lines = set(current_lines)
            else:
                prev_lines.update(current_lines)

        return cleaned

    def _write_srt(self, entries, out_path):
        with open(out_path, 'w', encoding='utf-8') as f:
            for idx, entry in enumerate(entries, 1):
                f.write(f"{idx}\n")
                f.write(f"{entry['time']}\n")
                f.write(f"{entry['text']}\n\n")
