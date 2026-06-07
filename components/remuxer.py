import os
import re
import subprocess


class Remuxer:
    # ISO 639-1 (two-letter) to ISO 639-2/B (three-letter) mapping for mov_text
    _LANG_TO_THREE = {
        'ar': 'ara', 'da': 'dan', 'de': 'deu', 'el': 'ell', 'en': 'eng',
        'es': 'spa', 'fi': 'fin', 'fr': 'fra', 'he': 'heb', 'hi': 'hin',
        'hu': 'hun', 'id': 'ind', 'it': 'ita', 'ja': 'jpn', 'ko': 'kor',
        'nl': 'nld', 'no': 'nor', 'pl': 'pol', 'pt': 'por', 'ro': 'ron',
        'ru': 'rus', 'sv': 'swe', 'th': 'tha', 'tr': 'tur', 'uk': 'ukr',
        'vi': 'vie', 'zh': 'zho',
    }

    @staticmethod
    def _to_three_letter(lang):
        return Remuxer._LANG_TO_THREE.get(lang, lang)

    def __init__(self, logger):
        self.logger = logger

    def _ffprobe_binary(self):
        path = os.environ.get('FFMPEG_PATH', '')
        if path:
            return os.path.join(os.path.dirname(path), 'ffprobe') + ('.exe' if os.name == 'nt' else '')
        return 'ffprobe' + ('.exe' if os.name == 'nt' else '')

    def _run_ffprobe(self, args):
        binary = self._ffprobe_binary()
        try:
            result = subprocess.run([binary] + args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
            return result.stdout
        except FileNotFoundError:
            self.logger.error("ffprobe not found")
            return ''
        except subprocess.TimeoutExpired:
            self.logger.error("ffprobe timed out")
            return ''
        except Exception as e:
            self.logger.error(f"ffprobe error: {e}")
            return ''

    def _ffmpeg_binary(self):
        return os.environ.get('FFMPEG_PATH', 'ffmpeg')

    def _run_ffmpeg(self, args):
        cmd = [self._ffmpeg_binary(), '-y'] + args
        self.logger.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        if result.returncode != 0:
            tail = result.stderr[-500:]
            raise RuntimeError(f"FFmpeg error: {tail}")
        return result

    def convert_video(self, input_path, output_path):
        self.logger.info(f"Converting video: {input_path} -> {output_path}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        self._run_ffmpeg([
            '-i', input_path,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            output_path,
        ])
        return output_path

    def convert_audio(self, input_path, output_path):
        self.logger.info(f"Converting audio: {input_path} -> {output_path}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        self._run_ffmpeg([
            '-i', input_path,
            '-q:a', '0',
            '-map', 'a',
            output_path,
        ])
        return output_path

    @staticmethod
    def _extract_srt_text(srt_path):
        lines = []
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        for block in re.split(r'\n\s*\n', content.strip()):
            parts = block.split('\n', 2)
            if len(parts) == 3:
                text = parts[2].replace('\n', ' ').strip()
                if text:
                    lines.append(text)
        return '\n'.join(lines)

    def _embed_lyrics_metadata(self, audio_path, subtitle_files):
        try:
            from mutagen.mp4 import MP4, MP4FreeForm
        except ImportError:
            self.logger.warn("mutagen not available, skipping lyrics metadata")
            return
        try:
            all_lyrics = {}
            for lang, sub_path in subtitle_files.items():
                text = self._extract_srt_text(sub_path)
                if text:
                    all_lyrics[lang] = text
            if not all_lyrics:
                return
            combined = '\n\n'.join(
                f"[{lang.upper()}]\n{text}" for lang, text in all_lyrics.items()
            )
            mp4 = MP4(audio_path)
            mp4['©lyr'] = combined
            mp4['----:com.apple.iTunes:LYRICS'] = MP4FreeForm(combined.encode('utf-8'))
            mp4.save()
            self.logger.info(f"Embedded lyrics metadata into audio ({len(all_lyrics)} languages)")
        except Exception as e:
            self.logger.warn(f"Failed to embed lyrics metadata: {e}")

    def get_chapters(self, video_path):
        probe = self._run_ffprobe(['-v', 'quiet', '-print_format', 'json', '-show_chapters', video_path])
        if not probe:
            return []
        import json
        data = json.loads(probe)
        return data.get('chapters', [])

    def split_by_chapters(self, video_path, output_dir, title, ext='mp4'):
        chapters = self.get_chapters(video_path)
        if not chapters:
            self.logger.info("No chapters found")
            return []

        os.makedirs(output_dir, exist_ok=True)
        results = []
        base = self._sanitize(title)

        for i, ch in enumerate(chapters):
            start = float(ch['start_time'])
            end = float(ch['end_time'])
            ch_title = ch.get('tags', {}).get('title', f'Chapter {i+1}')
            safe_title = self._sanitize(ch_title)
            output = os.path.join(output_dir, f"{base} - {safe_title}.{ext}")

            self._run_ffmpeg([
                '-i', video_path,
                '-ss', str(start),
                '-to', str(end),
                '-c', 'copy',
                output,
            ])
            results.append(output)

        return results

    @staticmethod
    def _sanitize(name):
        return re.sub(r'[<>:"/\\|?*]', '_', name).strip()

    def merge_video_audio(self, video_path, audio_path, output_path):
        self.logger.info(f"Merging video: {video_path} + audio: {audio_path}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self._run_ffmpeg([
            '-i', video_path,
            '-i', audio_path,
            '-c:v', 'copy',
            '-c:a', 'copy',
            output_path,
        ])
        return output_path

    def embed_subtitles_into_audio(self, audio_path, subtitle_files, output_path):
        if not subtitle_files:
            self.logger.warn("No subtitles to embed into audio")
            return audio_path

        langs = list(subtitle_files.keys())
        sub_count = len(subtitle_files)
        self.logger.info(f"Embedding {sub_count} subtitle track(s) + lyrics tag into audio")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        cmd = ['-i', audio_path]
        for sub_path in subtitle_files.values():
            cmd.extend(['-i', sub_path])

        cmd.extend(['-map', '0:a', '-map', '0:v?'])
        for i in range(sub_count):
            cmd.extend(['-map', f'{i+1}:s'])
        cmd.extend(['-c:a', 'copy', '-c:v', 'copy', '-c:s', 'mov_text'])
        for i, lang in enumerate(langs):
            three = self._to_three_letter(lang)
            cmd.extend([f'-metadata:s:s:{i}', f'language={three}'])
        cmd.append(output_path)

        self._run_ffmpeg(cmd)
        self._embed_lyrics_metadata(output_path, subtitle_files)
        return output_path

    @staticmethod
    def _ts_to_ms(ts):
        ts = ts.replace(',', '.')
        h, m, s = ts.split(':')
        s, ms = s.split('.')
        return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)

    @staticmethod
    def _ms_to_ts(ms):
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    def split_subtitle_lines(srt_path):
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        blocks = re.split(r'\n\s*\n', content.strip())
        new_blocks = []
        counter = 1
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
            time_line = lines[1]
            text_lines = lines[2:]
            if len(text_lines) <= 1:
                new_blocks.append(f"{counter}\n{time_line}\n{text_lines[0]}")
                counter += 1
                continue
            m = re.match(r'(\d{2}:\d{2}:\d{2}[,\\.]\d{3}) --> (\d{2}:\d{2}:\d{2}[,\\.]\d{3})', time_line)
            if not m:
                continue
            start_ms = Remuxer._ts_to_ms(m.group(1))
            end_ms = Remuxer._ts_to_ms(m.group(2))
            total_dur = end_ms - start_ms
            total_chars = sum(len(t) for t in text_lines)
            cur = start_ms
            for i, text in enumerate(text_lines):
                ratio = len(text) / total_chars if total_chars > 0 else 1.0 / len(text_lines)
                nxt = cur + int(total_dur * ratio)
                new_blocks.append(f"{counter}\n{Remuxer._ms_to_ts(cur)} --> {Remuxer._ms_to_ts(nxt)}\n{text}")
                counter += 1
                cur = nxt
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(new_blocks))
        return srt_path

    def convert_subtitle_to_srt(self, sub_path):
        ext = os.path.splitext(sub_path)[1].lower()
        if ext == '.srt':
            return sub_path
        out_path = os.path.splitext(sub_path)[0] + '.srt'
        self.logger.info(f"Converting subtitle: {sub_path} -> {out_path}")
        self._run_ffmpeg([
            '-i', sub_path,
            out_path,
        ])
        return out_path if os.path.exists(out_path) else sub_path

    def embed_subtitles(self, video_path, subtitle_files, output_path):
        if not subtitle_files:
            self.logger.warn("No subtitles to embed")
            return video_path

        langs = list(subtitle_files.keys())
        self.logger.info(f"Embedding {len(subtitle_files)} subtitle tracks into {video_path}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        cmd = ['-i', video_path]
        for sub_path in subtitle_files.values():
            cmd.extend(['-i', sub_path])

        cmd.extend(['-map', '0:v', '-map', '0:a'])
        for i in range(len(subtitle_files)):
            cmd.extend(['-map', f'{i+1}:s'])
        cmd.extend(['-c:v', 'copy', '-c:a', 'copy', '-c:s', 'mov_text'])
        for i, lang in enumerate(langs):
            three = self._to_three_letter(lang)
            cmd.extend([f'-metadata:s:s:{i}', f'language={three}'])
        cmd.append(output_path)

        self._run_ffmpeg(cmd)
        return output_path
