import os
import json
import uuid
import base64
import subprocess
import sys
import shutil
import time
import tarfile
import io
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization

REGISTER_URL = 'https://api.cloudflareclient.com/v0a2158/reg'
WP_API = 'https://api.github.com/repos/octeep/wireproxy/releases/latest'
WP_PORT = 1080


class WarpManager:
    def __init__(self, config_dir, logger):
        self.config_dir = Path(config_dir) / 'warp'
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / 'warp.json'
        self._process = None
        self.logger = logger

    def _gen_keypair(self):
        private = x25519.X25519PrivateKey.generate()
        priv_b64 = base64.b64encode(
            private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
        ).decode()
        pub_b64 = base64.b64encode(
            private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        ).decode()
        return priv_b64, pub_b64

    def register(self):
        import requests
        private_key, public_key = self._gen_keypair()
        install_id = str(uuid.uuid4())
        fwt = os.urandom(32).hex()

        self.logger.info("Registering WARP device...")
        r = requests.post(REGISTER_URL, json={
            'key': public_key,
            'install_id': install_id,
            'fcm_token': fwt,
            'referer': '',
            'warp_enabled': True,
            'locale': 'en_US',
        }, headers={
            'User-Agent': 'okhttp/3.12.1',
            'Content-Type': 'application/json; charset=UTF-8',
        }, timeout=15)

        if r.status_code != 200:
            raise RuntimeError(f"WARP registration failed: {r.status_code} {r.text[:200]}")

        j = r.json()
        cfg = j.get('config', {})
        iface = cfg.get('interface', {})
        peers = cfg.get('peers', [])
        if not peers:
            raise RuntimeError("No peers in WARP config")

        peer = peers[0]
        addresses = iface.get('addresses', {})

        config = {
            'private_key': private_key,
            'address_v4': addresses.get('v4', '172.16.0.2'),
            'address_v6': addresses.get('v6', ''),
            'dns': iface.get('dns', ['1.1.1.1']),
            'peer_public_key': peer.get('public_key'),
            'peer_endpoint': peer.get('endpoint', {}).get('host', 'engage.cloudflareclient.com:2408'),
        }

        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        self.logger.info(f"WARP registered: {config['address_v4']}")
        return config

    def load_config(self):
        if not self.config_file.exists():
            return None
        with open(self.config_file) as f:
            return json.load(f)

    def is_connected(self):
        return self._process is not None and self._process.poll() is None

    def _wp_binary(self):
        if getattr(sys, 'frozen', False):
            base = Path(sys._MEIPASS)
        else:
            base = Path(__file__).parent.parent
        name = 'wireproxy.exe' if os.name == 'nt' else 'wireproxy'
        path = base / name
        if path.exists():
            return str(path)
        cached = self.config_dir / name
        if cached.exists():
            return str(cached)
        return shutil.which(name)

    def _download_wp(self):
        import requests
        self.logger.info("Downloading wireproxy (userspace WireGuard, no admin needed)...")
        try:
            api_r = requests.get(WP_API, timeout=15)
            data = api_r.json()
            platform = 'windows_amd64' if os.name == 'nt' else 'linux_amd64'
            url = None
            for asset in data.get('assets', []):
                if platform in asset['name'] and asset['name'].endswith('.tar.gz'):
                    url = asset['browser_download_url']
                    break
            if not url:
                raise RuntimeError(f"No wireproxy asset for {platform}")
            self.logger.info(f"Fetching {url}...")
            r = requests.get(url, timeout=60)
            tar = tarfile.open(fileobj=io.BytesIO(r.content))
            exe_name = 'wireproxy.exe' if os.name == 'nt' else 'wireproxy'
            for m in tar.getmembers():
                if m.name.endswith(exe_name) or m.name == exe_name:
                    with tar.extractfile(m) as src, open(self.config_dir / exe_name, 'wb') as dst:
                        dst.write(src.read())
                    break
            path = self.config_dir / exe_name
            if os.name != 'nt':
                path.chmod(0o755)
            self.logger.info(f"wireproxy downloaded to {path}")
            return str(path)
        except Exception as e:
            self.logger.warn(f"Failed to download wireproxy: {e}")
            return None

    def _write_conf(self, cfg):
        conf_path = self.config_dir / 'wireproxy.conf'
        dns = ', '.join(cfg['dns'])
        with open(conf_path, 'w') as f:
            f.write('[Interface]\n')
            f.write(f'PrivateKey = {cfg["private_key"]}\n')
            f.write(f'Address = {cfg["address_v4"]}/32\n')
            if cfg.get('address_v6'):
                f.write(f'Address = {cfg["address_v6"]}/128\n')
            f.write(f'DNS = {dns}\n')
            f.write('\n[Peer]\n')
            f.write(f'PublicKey = {cfg["peer_public_key"]}\n')
            f.write(f'Endpoint = {cfg["peer_endpoint"]}\n')
            f.write('AllowedIPs = 0.0.0.0/0, ::/0\n')
            f.write('\n[Socks5]\n')
            f.write(f'BindAddress = 127.0.0.1:{WP_PORT}\n')
        return conf_path

    def connect(self):
        if self.is_connected():
            return True

        cfg = self.load_config()
        if not cfg:
            cfg = self.register()

        wp = self._wp_binary()
        if not wp:
            self.logger.warn("wireproxy not found, downloading...")
            wp = self._download_wp()

        if not wp:
            self.logger.warn(
                "Could not get wireproxy binary. "
                "Install wireproxy from https://github.com/octeep/wireproxy"
            )
            return False

        conf_path = self._write_conf(cfg)

        self.logger.info(f"Starting wireproxy (SOCKS5 :{WP_PORT})...")

        try:
            self._process = subprocess.Popen(
                [wp, '-c', str(conf_path)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=str(self.config_dir)
            )
            time.sleep(2)
            if self._process.poll() is not None:
                stderr = self._process.stderr.read().decode(errors='replace')[:300] if self._process.stderr else ''
                raise RuntimeError(f"wireproxy exited immediately: {stderr}")

            self.logger.info(f"WARP tunnel connected (SOCKS5 :{WP_PORT})")
            return True
        except Exception as e:
            self.logger.warn(f"WARP tunnel failed: {e}")
            self.disconnect()
            return False

    def disconnect(self):
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
            self.logger.info("WARP tunnel disconnected")
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/f', '/im', 'wireproxy.exe'], capture_output=True, timeout=5)
            else:
                subprocess.run(['pkill', '-f', 'wireproxy'], capture_output=True, timeout=5)
        except Exception:
            pass

    def get_proxy_url(self):
        if self.is_connected():
            return f'socks5://127.0.0.1:{WP_PORT}'
        return None

    def _get_ip_location(self, ip, proxy_url=None):
        import requests
        try:
            proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None
            r = requests.get(f'http://ip-api.com/json/{ip}?fields=status,country,regionName,city,isp,query', timeout=5, proxies=proxies)
            d = r.json()
            if d.get('status') == 'success':
                parts = [d.get('city', ''), d.get('regionName', ''), d.get('country', '')]
                loc = ', '.join(p for p in parts if p)
                isp = d.get('isp', '')
                return loc, isp
        except Exception:
            pass
        return '?', '?'

    def show_status(self, cli):
        import requests
        tunnel_active = self.is_connected()
        current = '?'
        via_warp = '?'

        try:
            r = requests.get('https://api.ipify.org?format=json', timeout=10)
            current = r.json().get('ip', '?')
        except Exception as e:
            current = f"Error: {e}"

        if tunnel_active:
            proxy_url = f'socks5://127.0.0.1:{WP_PORT}'
            try:
                r = requests.get('https://api.ipify.org?format=json', timeout=10,
                                 proxies={'http': proxy_url, 'https': proxy_url})
                via_warp = r.json().get('ip', '?')
            except Exception as e:
                via_warp = f"Error: {e}"

        cli.console.print(f"\n[bold cyan]Connection Status[/]")
        if tunnel_active:
            cli.console.print(f"  Status:       [green]Connected[/]")
            cli.console.print(f"  Your IP:      [green]{current}[/]")
            cli.console.print(f"  Via WARP:     [green]{via_warp}[/]")
            if current != via_warp and 'Error' not in str(via_warp) and 'Error' not in str(current):
                cli.console.print("  [bold green]WARP is working — IP changed[/]")
            elif current == via_warp:
                cli.console.print("  [bold yellow]WARP proxy found but IP unchanged (check route)[/]")
        else:
            cli.console.print(f"  Status:       [red]Disconnected[/]")
            cli.console.print(f"  Your IP:      [green]{current}[/]")
        cli.console.print()
        return current, via_warp

    def show_public_ip(self, cli):
        import requests
        import urllib.request
        current = '?'
        via_warp = '?'
        current_loc = '?'
        current_isp = '?'
        warp_loc = '?'
        warp_isp = '?'
        tunnel_active = self.is_connected()
        proxy_source = None
        proxy_url = None

        try:
            r = requests.get('https://api.ipify.org?format=json', timeout=10)
            current = r.json().get('ip', '?')
            current_loc, current_isp = self._get_ip_location(current)
        except Exception as e:
            current = f"Error: {e}"

        if tunnel_active:
            proxy_url = f'socks5://127.0.0.1:{WP_PORT}'
            proxy_source = "Managed tunnel"
        else:
            for port in [40000, 1080, 9050]:
                test_url = f'socks5://127.0.0.1:{port}'
                try:
                    proxy_hdlr = urllib.request.ProxyHandler({'http': test_url, 'https': test_url})
                    opener = urllib.request.build_opener(proxy_hdlr)
                    r = opener.open('https://api.ipify.org?format=json', timeout=3)
                    ip = json.loads(r.read()).get('ip', '')
                    if ip:
                        proxy_url = test_url
                        proxy_source = f"SOCKS5 :{port}"
                        tunnel_active = True
                        break
                except Exception:
                    continue

        if proxy_url:
            try:
                r = requests.get('https://api.ipify.org?format=json', timeout=10,
                                 proxies={'http': proxy_url, 'https': proxy_url})
                via_warp = r.json().get('ip', '?')
                warp_loc, warp_isp = self._get_ip_location(via_warp, proxy_url)
            except Exception as e:
                via_warp = f"Error: {e}"

        cli.console.print(f"\n[bold cyan]IP Address Check[/]")
        cli.console.print(f"  Direct IP:    [green]{current}[/]")
        if '?' not in current_loc:
            cli.console.print(f"  Location:     [dim]{current_loc} ({current_isp})[/]")
        if proxy_source:
            cli.console.print(f"  Proxy found:  [yellow]{proxy_source}[/]")
        cli.console.print(f"  WARP tunnel:  [yellow]{'Active' if tunnel_active else 'Inactive'}[/]")
        if proxy_url and '?' not in via_warp:
            cli.console.print(f"  Via WARP:     [green]{via_warp}[/]")
            if '?' not in warp_loc:
                cli.console.print(f"  Location:     [dim]{warp_loc} ({warp_isp})[/]")
        elif proxy_url:
            cli.console.print(f"  Via WARP:     [green]{via_warp}[/]")
        cli.console.print()

        if tunnel_active and current != via_warp and 'Error' not in str(via_warp) and 'Error' not in str(current):
            cli.console.print("  [bold green]WARP is working — IP changed[/]")
        elif tunnel_active and current == via_warp:
            cli.console.print("  [bold yellow]WARP proxy found but IP unchanged (check route)[/]")
        cli.console.print()
        return current, via_warp