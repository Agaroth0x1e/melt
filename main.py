#!/usr/bin/env python3
import os
import sys
import subprocess

VERSION = '1.0.1'

HELP_TEXT = f"""
MelT v{VERSION} - YouTube Downloader CLI

USAGE:
  python main.py                    Interactive mode (default)
  python main.py --help             Show this help message
  python main.py --version          Show version
  python main.py --resume           Resume interrupted download queue

DESCRIPTION:
  Download video, audio, and subtitles from YouTube with a
  modern CLI interface (MelT v{VERSION}). Supports playlists,
  thumbnail embedding, subtitle cleaning, SponsorBlock,
  and parallel downloads.

FEATURES:
  - Single video / playlist / multi-URL / batch file (@file.txt)
  - Video (mp4) or Audio (m4a) with thumbnail & subtitle embedding
  - Automatic subtitle download with roll-up caption cleaning
  - Configurable parallel downloads (multi-threaded)
  - Archive system to avoid re-downloading duplicates
  - SponsorBlock integration (auto-skip sponsored segments)
  - Download queue persistence (resume crashes with --resume)
  - Dry-run mode to preview before downloading
  - Rate limiting and cookies file support
  - Pre-built standalone .exe (ffmpeg included)
  - Fully configurable via config/config.json

REQUIREMENTS:
  - ffmpeg (bundled in .exe, or system install)
  - Node.js (optional - 2x yt-dlp speed)

CONFIGURATION:
  See config/config.json for all available options.

EXAMPLES:
  python main.py                    Start interactive session
  python main.py --resume           Resume interrupted download queue
  python main.py --version          Show version
  python main.py --help             Show this help
"""


def _is_bundled():
    return getattr(sys, 'frozen', False)


def _bundle_dir():
    if _is_bundled():
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _exe_dir():
    if _is_bundled():
        return os.path.abspath(os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def find_ffmpeg():
    locations = [
        os.path.join(_bundle_dir(), 'ffmpeg.exe'),
        os.path.join(_exe_dir(), 'ffmpeg.exe'),
        'ffmpeg',
    ]
    for loc in locations:
        try:
            r = subprocess.run(
                [loc, '-version'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            if r.returncode == 0:
                return loc
        except FileNotFoundError:
            continue
    return None


def check_nodejs():
    try:
        r = subprocess.run(
            ['node', '--version'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return r.returncode == 0
    except FileNotFoundError:
        return False


def show_help():
    print(HELP_TEXT)
    sys.exit(0)


def main():
    if '-h' in sys.argv or '--help' in sys.argv:
        show_help()
    if '--version' in sys.argv:
        print(f"MelT v{VERSION}")
        sys.exit(0)

    resume = '--resume' in sys.argv

    ffmpeg_path = find_ffmpeg()
    if not ffmpeg_path:
        print("ERROR: ffmpeg not found.")
        print("  The standalone .exe bundles ffmpeg automatically.")
        print("  If running from source, install ffmpeg:")
        print("    Windows: scoop install ffmpeg")
        print("    macOS:   brew install ffmpeg")
        print("    Linux:   sudo apt install ffmpeg")
        print("    Termux:  pkg install ffmpeg")
        input("\nPress Enter to exit...")
        sys.exit(1)

    os.environ['FFMPEG_PATH'] = ffmpeg_path

    if not check_nodejs():
        os.environ['YTDLP_NO_NODE'] = '1'

    try:
        import importlib.util
        for mod in ('rich', 'yt_dlp'):
            if importlib.util.find_spec(mod) is None:
                raise ImportError(mod)
    except ImportError as e:
        print(f"ERROR: Missing dependency: {e}")
        print("If running from source: pip install -r requirements.txt")
        input("\nPress Enter to exit...")
        sys.exit(1)

    from utils.config import Config
    from utils.logger import Logger
    from utils.archive import Archive
    from utils.failed import FailedTracker
    from utils.cli import CLI
    from mother_script import MotherScript

    config = Config()

    errors = config.validate()
    if errors:
        print("ERROR: Invalid configuration:")
        for e in errors:
            print(f"  - {e}")
        print("Fix config/config.json or delete it to regenerate defaults.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    log_path = config.resolve_path(config['general']['log_file'])
    archive_path = config.resolve_path(config['general']['archive_file'])
    failed_path = config.resolve_path(config['general']['failed_file'])

    logger = Logger(log_path)
    archive = Archive(archive_path)
    failed = FailedTracker(failed_path)
    cli = CLI(config)

    logger.info("MelT started")

    try:
        mother = MotherScript(config, logger, archive, failed, cli)
        mother.run(resume)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting.")
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\nFatal error: {e}")
        if config['general'].get('enable_sounds', True):
            from utils.notification import notify_async as _nfy
            _nfy("Fatal Error", f"{e}", "fatal_error")

    logger.info("MelT finished")

    if _is_bundled():
        input("\nPress Enter to exit...")


if __name__ == '__main__':
    main()
