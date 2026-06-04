import os
import sys
import subprocess
import threading


def _sounds_dir():
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'sounds')
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sounds')


def play_sound(name, block=False, config=None):
    custom = None
    if config and 'sounds' in config.config:
        custom = config['sounds'].get(name, '')
    path = custom if custom else os.path.join(_sounds_dir(), f'{name}.wav')
    if not os.path.exists(path):
        return

    fn = subprocess.run if block else subprocess.Popen
    kwargs = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.name == 'nt' and not block:
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

    try:
        for exe in ('ffplay', 'ffmpeg'):
            candidate = os.path.join(os.path.dirname(_sounds_dir()), '..', f'{exe}.exe' if os.name == 'nt' else exe)
            candidate = os.path.normpath(candidate)
            if os.path.exists(candidate):
                fn([candidate, '-nodisp', '-autoexit', '-loglevel', 'quiet', path], **kwargs)
                return
    except Exception:
        pass

    try:
        fn(['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet', path], **kwargs)
    except FileNotFoundError:
        try:
            fn(['ffmpeg', '-nodisp', '-autoexit', '-loglevel', 'quiet', path], **kwargs)
        except FileNotFoundError:
            pass


def _notify_desktop(title, message):
    try:
        from plyer import notification
        notification.notify(title=title, message=message, app_name='MelT', timeout=5)
        return True
    except Exception:
        pass
    return False


def _notify_termux(title, message, sound_name=None):
    if not os.environ.get('TERMUX_VERSION'):
        return False
    cmd = ['termux-notification', '-t', title, '-c', message]
    if sound_name:
        spath = os.path.join(_sounds_dir(), f'{sound_name}.wav')
        if os.path.exists(spath):
            cmd.extend(['--sound', spath])
    try:
        subprocess.run(cmd, capture_output=True)
        return True
    except Exception:
        pass
    return False


def notify(title, message, sound_name=None, config=None):
    if sound_name:
        play_sound(sound_name, config=config)

    if _notify_termux(title, message, sound_name):
        return
    _notify_desktop(title, message)


def notify_async(title, message, sound_name=None, config=None):
    t = threading.Thread(target=notify, args=(title, message, sound_name, config), daemon=True)
    t.start()
