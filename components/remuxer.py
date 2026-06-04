import os
import re
import subprocess


class Remuxer:
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
            result = subprocess.run([binary] + args, capture_output=True, text=True, timeout=60)
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
            text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg error: {result.stderr[:500]}")
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

    def _embed_lyrics_metadata(self, audio_path, subtitle_path):
        try:
            from mutagen.mp4 import MP4
        except ImportError:
            self.logger.warn("mutagen not available, skipping lyrics metadata")
            return
        try:
            lyrics = self._extract_srt_text(subtitle_path)
            if not lyrics:
                return
            mp4 = MP4(audio_path)
            mp4['©lyr'] = lyrics
            mp4.save()
            self.logger.info("Embedded lyrics metadata into audio")
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

    def embed_subtitles_into_audio(self, audio_path, subtitle_path, output_path):
        if not subtitle_path or not os.path.exists(subtitle_path):
            self.logger.warn("No subtitles to embed into audio")
            return audio_path

        self.logger.info(f"Embedding subtitles: {subtitle_path} into {audio_path}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        sub_ext = os.path.splitext(subtitle_path)[1].lower()

        self._run_ffmpeg([
            '-i', audio_path,
            '-f', sub_ext.lstrip('.'),
            '-i', subtitle_path,
            '-c:a', 'copy',
            '-c:s', 'mov_text',
            '-metadata:s:s:0', 'language=eng',
            output_path,
        ])
        self._embed_lyrics_metadata(output_path, subtitle_path)
        return output_path

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

    def embed_subtitles(self, video_path, subtitle_path, output_path):
        if not subtitle_path or not os.path.exists(subtitle_path):
            self.logger.warn("No subtitles to embed")
            return video_path

        self.logger.info(f"Embedding subtitles: {subtitle_path} into {video_path}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        sub_ext = os.path.splitext(subtitle_path)[1].lower()

        self._run_ffmpeg([
            '-i', video_path,
            '-f', sub_ext.lstrip('.'),
            '-i', subtitle_path,
            '-c:v', 'copy',
            '-c:a', 'copy',
            '-c:s', 'mov_text',
            '-metadata:s:s:0', 'language=eng',
            output_path,
        ])
        return output_path
