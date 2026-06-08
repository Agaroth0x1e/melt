import os
import sys
import urllib.parse
import yt_dlp
from components.remuxer import Remuxer

class YtdlpLogger:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


class Downloader:
    _proxy_cache = None

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self._info_cache = {}
        self._flat_cache = {}
        self._flat = config.get('download', {}).get('extract_flat', {}).get('inspect', True)

    def _resolve(self, path):
        return path if os.path.isabs(path) else self.config.resolve_path(path)

    def _media_extensions(self):
        return {'.mp4', '.mkv', '.webm', '.m4a', '.mp3', '.mka', '.opus', '.ogg', '.wav', '.aac', '.flac'}

    def _find_media_file(self, directory):
        candidates = []
        for f in os.listdir(directory):
            ext = os.path.splitext(f)[1].lower()
            if ext in self._media_extensions():
                candidates.append(os.path.join(directory, f))
        if candidates:
            return max(candidates, key=os.path.getmtime)
        return None

    def _find_subtitle_files(self, directory, languages, prefer_human=True):
        result = {}
        for lang in languages:
            found = self._find_single_subtitle(directory, lang, prefer_human)
            if found:
                result[lang] = found
        return result

    def _find_single_subtitle(self, directory, lang, prefer_human=True):
        if not os.listdir(directory):
            return None
        files = sorted(os.listdir(directory), reverse=True)
        candidates = {'human': [], 'auto': []}
        for f in files:
            lower = f.lower()
            if '.clean.' in lower:
                continue
            is_sub = lower.endswith(f'.{lang}.srt') or lower.endswith(f'.{lang}.vtt') \
                     or lower.endswith('.srt') or lower.endswith('.vtt')
            if not is_sub:
                continue
            if lang in lower and lower.count(lang) == 1:
                candidates['human'].append(f)
            else:
                candidates['auto'].append(f)
        pick = candidates['human'] if prefer_human and candidates['human'] else candidates['auto']
        return os.path.join(directory, pick[0]) if pick else None

    def get_video_info(self, url, force=False):
        if not force and url in self._info_cache:
            return self._info_cache[url]
        info_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
        }
        with yt_dlp.YoutubeDL(info_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                self._info_cache[url] = info
                return info
            except Exception as e:
                raise RuntimeError(f"Failed to fetch video info: {e}")

    def is_playlist(self, url):
        if url in self._flat_cache:
            return bool(self._flat_cache[url].get('entries'))
        try:
            flat_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': self._flat, 'skip_download': True}
            with yt_dlp.YoutubeDL(flat_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                self._flat_cache[url] = info
                return bool(info.get('entries'))
        except Exception:
            return False

    def get_playlist_entries(self, url):
        if url in self._flat_cache:
            info = self._flat_cache[url]
        else:
            flat_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': self._flat, 'skip_download': True}
            with yt_dlp.YoutubeDL(flat_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                self._flat_cache[url] = info

        if not info.get('entries') and self._has_list_param(url):
            pl_url = f"https://www.youtube.com/playlist?list={urllib.parse.parse_qs(urllib.parse.urlparse(url).query)['list'][0]}"
            if pl_url not in self._flat_cache:
                try:
                    flat_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': self._flat, 'skip_download': True}
                    with yt_dlp.YoutubeDL(flat_opts) as ydl:
                        pl_info = ydl.extract_info(pl_url, download=False)
                        self._flat_cache[pl_url] = pl_info
                        if pl_info.get('entries'):
                            info = pl_info
                            self._flat_cache[url] = pl_info
                except Exception:
                    pass

        entries = []
        title = info.get('title', 'Unknown')
        pid = info.get('id', '')
        if 'entries' in info and info['entries']:
            for entry in info['entries']:
                if entry:
                    entries.append({
                        'id': entry.get('id', ''),
                        'title': entry.get('title', 'Unknown'),
                        'url': f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                        'playlist': title,
                        'playlist_id': pid,
                    })
        return entries, title, pid

    @staticmethod
    def _has_list_param(url):
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            return bool(qs.get('list'))
        except Exception:
            return False

    def inspect_url(self, url):
        if url not in self._flat_cache:
            flat_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': self._flat, 'skip_download': True}
            with yt_dlp.YoutubeDL(flat_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                self._flat_cache[url] = info
        info = self._flat_cache[url]
        entries = info.get('entries')
        is_pl = bool(entries) or self._has_list_param(url)
        return {
            'url': url,
            'is_playlist': is_pl,
            'title': info.get('title', 'Unknown'),
            'entry_count': len(entries) if entries else 0,
            'id': info.get('id', ''),
        }

    def get_single_entry(self, url):
        info = self.get_video_info(url)
        return {
            'id': info.get('id', ''),
            'title': info.get('title', 'Unknown'),
            'url': url,
            'playlist': None,
            'playlist_id': None,
        }

    def get_single_entry_fast(self, url):
        if url in self._flat_cache:
            info = self._flat_cache[url]
        else:
            flat_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': self._flat, 'skip_download': True}
            with yt_dlp.YoutubeDL(flat_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                self._flat_cache[url] = info
        return {
            'id': info.get('id', ''),
            'title': info.get('title', 'Unknown'),
            'url': url,
            'playlist': None,
            'playlist_id': None,
        }

    def fetch_formats(self, url):
        opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
        opts.update(self._cookies_opts())
        opts.update(self._cookies_from_browser_opts())
        opts.update(self._proxy_opts())
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        raw = info.get('formats', [])
        rows = []
        for f in raw:
            if f.get('vcodec') == 'none' and f.get('acodec') == 'none':
                continue
            fmt_id = f.get('format_id', '?')
            ext = f.get('ext', '?')
            note = f.get('format_note', '')
            vcodec = f.get('vcodec', 'none')
            acodec = f.get('acodec', 'none')
            height = f.get('height', 0) or 0
            abr = f.get('abr', 0) or 0
            size = f.get('filesize') or f.get('filesize_approx', 0) or 0
            is_video = vcodec != 'none'
            is_audio = acodec != 'none' and vcodec == 'none'
            if is_video:
                label = f"{height}p"
                if note:
                    label = note
                codec = vcodec.split('.')[0][:6]
                row = (fmt_id, ext, 'video', label, codec, size)
            elif is_audio:
                codec = acodec.split('.')[0][:6]
                row = (fmt_id, ext, 'audio', f"{int(abr)}k", codec, size)
            else:
                continue
            rows.append(row)
        def _qual_val(q):
            q = q.rstrip('pk')
            return int(q) if q.isdigit() else 0
        rows.sort(key=lambda r: (r[2], -_qual_val(r[3])))
        return rows

    def _video_only_format_string(self):
        ext = self.config['video']['preferred_format']
        codec = self.config['video'].get('preferred_codec', 'h264')
        vcodec = {'h264': 'avc1', 'h265': 'hevc', 'vp9': 'vp9'}.get(codec, 'avc1')
        priorities = self.config['video'].get('quality_priority', ['480', '360', '720'])

        formats = []
        for q in priorities:
            formats.append(f"bestvideo[ext={ext}][vcodec^={vcodec}][height<={q}]")
        formats.append(f"bestvideo[ext={ext}][vcodec^={vcodec}][height<=1080][height>360]")
        formats.append(f"bestvideo[ext={ext}]")
        formats.append("bestvideo")

        return "/".join(formats)

    def _video_format_string(self):
        ext = self.config['video']['preferred_format']
        aext = self.config['audio']['preferred_format']
        codec = self.config['video'].get('preferred_codec', 'h264')
        vcodec = {'h264': 'avc1', 'h265': 'hevc', 'vp9': 'vp9'}.get(codec, 'avc1')
        priorities = self.config['video'].get('quality_priority', ['480', '360', '720'])

        formats = []
        for q in priorities:
            formats.append(f"bestvideo[ext={ext}][vcodec^={vcodec}][height<={q}]+bestaudio[ext={aext}]")
        formats.append(f"bestvideo[ext={ext}][vcodec^={vcodec}][height<=1080][height>360]+bestaudio[ext={aext}]")
        formats.append(f"bestvideo[ext={ext}]+bestaudio[ext={aext}]")
        formats.append("best")

        return "/".join(formats)

    def _audio_only_format_string(self):
        ext = self.config['audio']['preferred_format']
        priorities = self.config['audio'].get('quality_priority', ['128', '192', '264'])
        formats = []
        for q in priorities:
            q_int = int(q)
            formats.append(f"bestaudio[ext={ext}][abr<={q_int + 16}][abr>={max(0, q_int - 16)}]")
        formats.append(f"bestaudio[ext={ext}]")
        formats.append("bestaudio")
        return "/".join(formats)

    def _audio_format_string(self):
        ext = self.config['audio']['preferred_format']
        priorities = self.config['audio'].get('quality_priority', ['128', '192', '264'])

        formats = []
        for q in priorities:
            q_int = int(q)
            formats.append(f"bestaudio[ext={ext}][abr<={q_int + 16}][abr>={max(0, q_int - 16)}]")
        formats.append(f"bestaudio[ext={ext}]")
        formats.append("bestaudio")

        return "/".join(formats)

    def _progress_hook(self, d):
        if d['status'] == 'downloading':
            pct = d.get('_percent_str', '').strip()
            speed = d.get('_speed_str', '')
            eta = d.get('_eta_str', '')
            total = d.get('_total_bytes_str', '')
            parts = [p for p in [pct, speed, eta, total] if p]
            if parts:
                sys.stderr.write('\r[download] ' + ' • '.join(parts) + '    ')
                sys.stderr.flush()

    @staticmethod
    def _make_progress_hook(entry_idx, total):
        def hook(d):
            if d['status'] == 'downloading':
                pct = d.get('_percent_str', '').strip()
                speed = d.get('_speed_str', '')
                eta = d.get('_eta_str', '')
                size = d.get('_total_bytes_str', '')
                parts = [p for p in [pct, speed, eta, size] if p]
                if parts:
                    sys.stdout.write(f'\r[download {entry_idx}/{total}] ' + ' • '.join(parts) + '    ')
                    sys.stdout.flush()
        return hook

    def _cookies_opts(self):
        cf = self.config['network'].get('cookies_file', '')
        if cf:
            cf_path = self._resolve(cf)
            if os.path.exists(cf_path):
                return {'cookiefile': cf_path}
        return {}

    def _cookies_from_browser_opts(self):
        browser = self.config['network'].get('cookies_from_browser', '')
        if browser:
            return {'cookiesfrombrowser': (browser,)}
        return {}

    def _rate_limit_opts(self):
        val = self.config['network'].get('rate_limit', '')
        if val:
            return {'limit_rate': val}
        return {}

    def _sponsorblock_opts(self):
        if self.config['download'].get('sponsorblock', True):
            return {'sponsorblock_mark': 'all'}
        return {}

    def _ffmpeg_location_opts(self):
        path = os.environ.get('FFMPEG_PATH', '')
        if path:
            return {'ffmpeg_location': path}
        return {}

    def _proxy_opts(self):
        proxy_setting = self.config['network'].get('proxy', '')
        if proxy_setting and proxy_setting != 'auto':
            return {'proxy': proxy_setting}
        if proxy_setting == 'auto':
            found = self._detect_proxy()
            if found:
                self.logger.info(f"Auto-detected proxy: {found}")
                self.config['network']['proxy'] = found
                return {'proxy': found}
        return {}

    def _detect_proxy(self):
        if Downloader._proxy_cache is not None:
            return Downloader._proxy_cache
        candidates = []

        sys_proxy = self._get_system_proxy()
        if sys_proxy:
            candidates.append(sys_proxy)

        common_ports = [40000, 1080, 9050, 8118, 8080, 3128]
        for port in common_ports:
            candidates.append(('socks5', '127.0.0.1', port))
            candidates.append(('http', '127.0.0.1', port))

        seen = set()
        for scheme, host, port in candidates:
            key = (scheme, host, port)
            if key in seen:
                continue
            seen.add(key)
            if self._test_proxy(scheme, host, port):
                result = f"{scheme}://{host}:{port}"
                Downloader._proxy_cache = result
                self.logger.info(f"Proxy auto-detected locally: {result}")
                return result

        Downloader._proxy_cache = False
        return None

    @staticmethod
    def _get_system_proxy():
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as key:
                enabled, _ = winreg.QueryValueEx(key, 'ProxyEnable')
                if enabled:
                    server, _ = winreg.QueryValueEx(key, 'ProxyServer')
                    if server:
                        parts = server.split(':')
                        host = parts[0]
                        port = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 8080
                        return ('http', host, port)
        except Exception:
            pass
        return None

    @staticmethod
    def _test_proxy(scheme, host, port, timeout=2):
        try:
            import urllib.request
            proxy_url = f"{scheme}://{host}:{port}"
            proxy_hdlr = urllib.request.ProxyHandler({scheme: proxy_url})
            opener = urllib.request.build_opener(proxy_hdlr)
            opener.open('https://www.google.com', timeout=timeout)
            return True
        except Exception:
            return False

    def download_video(self, entry, job_dir, fmt_override=None, entry_idx=0, total=0):
        work_dir = self._resolve(job_dir)
        os.makedirs(work_dir, exist_ok=True)

        tmpl = self.config['download']['filename_template']
        outtmpl = os.path.join(work_dir, tmpl)

        merge_mode = self.config['download'].get('merge_mode', False)
        ph = self._make_progress_hook(entry_idx, total)

        if merge_mode:
            v_opts = {
                'format': fmt_override or self._video_only_format_string(),
                'outtmpl': outtmpl,
                'quiet': True,
                'no_warnings': True,
                'noprogress': True,
                'skip_download': False,
                'progress_hooks': [ph],
            }
            v_opts.update(self._cookies_opts())
            v_opts.update(self._cookies_from_browser_opts())
            v_opts.update(self._rate_limit_opts())
            v_opts.update(self._sponsorblock_opts())
            v_opts.update(self._ffmpeg_location_opts())
            v_opts.update(self._proxy_opts())

            self.logger.info(f"Downloading video stream (merge mode): {entry['title']}")
            with yt_dlp.YoutubeDL(v_opts) as ydl:
                try:
                    ydl.download([entry['url']])
                except Exception as e:
                    raise RuntimeError(f"Video stream download failed: {e}")

            v_path = self._find_media_file(work_dir)
            if not v_path:
                raise RuntimeError("Video stream download produced no file")

            a_opts = {
                'format': self._audio_only_format_string(),
                'outtmpl': outtmpl,
                'quiet': True,
                'no_warnings': True,
                'noprogress': True,
                'skip_download': False,
                'progress_hooks': [self._make_progress_hook(entry_idx, total)],
            }
            a_opts.update(self._cookies_opts())
            a_opts.update(self._cookies_from_browser_opts())
            a_opts.update(self._rate_limit_opts())
            a_opts.update(self._sponsorblock_opts())
            a_opts.update(self._ffmpeg_location_opts())
            a_opts.update(self._proxy_opts())

            self.logger.info(f"Downloading audio stream (merge mode): {entry['title']}")
            with yt_dlp.YoutubeDL(a_opts) as ydl:
                try:
                    ydl.download([entry['url']])
                except Exception as e:
                    raise RuntimeError(f"Audio stream download failed: {e}")

            a_path = self._find_media_file(work_dir)
            if not a_path:
                raise RuntimeError("Audio stream download produced no file")

            ext = self.config['video']['preferred_format']
            merged_path = os.path.join(work_dir, f"merged.{ext}")
            remuxer = Remuxer(self.logger)
            return remuxer.merge_video_audio(v_path, a_path, merged_path)

        ydl_opts = {
            'format': fmt_override or self._video_format_string(),
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            'skip_download': False,
            'progress_hooks': [self._make_progress_hook(entry_idx, total)],
        }
        ydl_opts.update(self._cookies_opts())
        ydl_opts.update(self._cookies_from_browser_opts())
        ydl_opts.update(self._rate_limit_opts())
        ydl_opts.update(self._sponsorblock_opts())
        ydl_opts.update(self._ffmpeg_location_opts())
        ydl_opts.update(self._proxy_opts())

        self.logger.info(f"Downloading video: {entry['title']}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([entry['url']])
                return self._find_media_file(work_dir)
            except Exception as e:
                raise RuntimeError(f"Download failed: {e}")

    def download_audio(self, entry, job_dir, fmt_override=None, entry_idx=0, total=0):
        work_dir = self._resolve(job_dir)
        os.makedirs(work_dir, exist_ok=True)

        tmpl = self.config['download']['filename_template']
        outtmpl = os.path.join(work_dir, tmpl)
        quality = self.config['audio']['default_quality']

        ydl_opts = {
            'format': fmt_override or self._audio_format_string(),
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            'skip_download': False,
            'progress_hooks': [self._make_progress_hook(entry_idx, total)],
        }

        ydl_opts.update(self._cookies_opts())
        ydl_opts.update(self._cookies_from_browser_opts())
        ydl_opts.update(self._rate_limit_opts())
        ydl_opts.update(self._sponsorblock_opts())
        ydl_opts.update(self._ffmpeg_location_opts())
        ydl_opts.update(self._proxy_opts())

        self.logger.info(f"Downloading audio: {entry['title']}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([entry['url']])
                return self._find_media_file(work_dir)
            except Exception as e:
                raise RuntimeError(f"Download failed: {e}")

    def download_subtitles(self, entry, job_dir):
        work_dir = self._resolve(job_dir)
        os.makedirs(work_dir, exist_ok=True)

        tmpl = self.config['download']['filename_template']
        outtmpl = os.path.join(work_dir, tmpl)
        raw_lang = self.config['subtitle']['language']
        languages = [l.strip() for l in raw_lang.split(',')] if ',' in raw_lang else [raw_lang]
        prefer_human = self.config['subtitle'].get('prefer_human', True)
        sub_fmt = self.config['subtitle'].get('preferred_format', 'srt')

        ydl_opts = {
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': languages,
            'subtitlesformat': sub_fmt,
            'logger': YtdlpLogger(),
        }

        ydl_opts.update(self._cookies_opts())
        ydl_opts.update(self._cookies_from_browser_opts())
        ydl_opts.update(self._ffmpeg_location_opts())
        ydl_opts.update(self._proxy_opts())

        self.logger.info(f"Downloading subtitles for: {entry['title']} (langs: {', '.join(languages)})")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([entry['url']])
        return self._find_subtitle_files(work_dir, languages, prefer_human)
