"""Official Sakura API/client integration, credentials stored only in private files."""
import configparser
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import urllib.request
from urllib.parse import urlsplit

from private_storage import write_json, write_private, private_directory

API = 'https://api.natfrp.com/v4'


class SakuraError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SakuraError('Sakura API redirects are not accepted')


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != 'https':
            raise SakuraError('Client download must remain HTTPS')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class SakuraAPI:
    def __init__(self, token=None):
        self.token = token
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, path, body=None, text=False):
        headers = {'User-Agent': 'AI-Doll-MCP/2.13.0'}
        if self.token:
            headers['Authorization'] = 'Bearer '+self.token
        if body is not None:
            headers['Content-Type'] = 'application/json'
        try:
            request = urllib.request.Request(API+path,
                data=json.dumps(body).encode() if body is not None else None, headers=headers)
            with self.opener.open(request, timeout=20) as response:
                raw = response.read(1048577)
                if len(raw)>1048576: raise SakuraError('Sakura response too large')
                return raw.decode('utf-8') if text else json.loads(raw)
        except Exception:
            raise SakuraError('Sakura request failed; check the locally saved token, network and tunnel ID') from None


def architecture():
    machine = platform.machine().lower()
    arch = {'amd64': 'amd64', 'x86_64': 'amd64', 'arm64': 'arm64', 'aarch64':'arm64',
            'x86':'386', 'i386':'386', 'i686':'386'}.get(machine)
    prefix = {'Windows':'windows', 'Linux':'linux', 'Darwin':'darwin'}.get(platform.system())
    if not arch or not prefix:
        raise SakuraError('Unsupported platform; install a verified official Sakura client manually')
    return prefix+'_'+arch


def install_client(folder, api=None):
    folder = private_directory(folder)
    catalog = (api or SakuraAPI()).request('/system/clients?download=true')
    release = catalog.get('frpc', {})
    version = release.get('ver','')
    artifact = release.get('archs',{}).get(architecture(), {})
    url, digest, size = artifact.get('url'), artifact.get('hash'), artifact.get('size')
    if (not re.fullmatch(r'[0-9.]+-sakura-[0-9]+', version) or not isinstance(url,str)
            or urlsplit(url).scheme != 'https' or not isinstance(digest,str)
            or not re.fullmatch('[0-9a-fA-F]{32}|[0-9a-fA-F]{64}',digest)
            or type(size) is not int or not 100000 <= size <= 100*1024*1024):
        raise SakuraError('Official client catalog did not contain a supported verified artifact')
    executable = folder / ('frpc.exe' if os.name == 'nt' else 'frpc')
    algorithm = 'md5' if len(digest)==32 else 'sha256'
    def valid():
        return executable.is_file() and executable.stat().st_size==size and hashlib.new(algorithm,executable.read_bytes()).hexdigest()==digest.lower()
    if not valid():
        partial = folder / 'frpc.download'
        try:
            opener = urllib.request.build_opener(HTTPSRedirect())
            request = urllib.request.Request(url,headers={'User-Agent':'AI-Doll-MCP/2.13.0'})
            with opener.open(request,timeout=30) as response, partial.open('wb') as handle:
                count = 0
                while chunk := response.read(65536):
                    count += len(chunk)
                    if count>size: raise SakuraError('Official client size mismatch')
                    handle.write(chunk)
            if partial.stat().st_size!=size or hashlib.new(algorithm,partial.read_bytes()).hexdigest()!=digest.lower():
                raise SakuraError('Official client checksum mismatch')
            os.replace(partial, executable)
        except SakuraError:
            raise
        except Exception:
            raise SakuraError('Official Sakura client download failed; no unverified file was executed') from None
        finally:
            partial.unlink(missing_ok=True)
    if os.name!='nt': executable.chmod(0o700)
    flags = subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    try:
        found = subprocess.run([str(executable),'-v'],capture_output=True,timeout=10,
                               creationflags=flags,check=True).stdout.decode('utf-8').strip()
        if not re.fullmatch(r'[0-9.]+-sakura-[0-9.]+',found):
            raise SakuraError('Executable is not an official Sakura frpc build')
    except Exception:
        raise SakuraError('Official client executable failed its version check') from None
    result = dict(version=found, catalog_version=version, version_label_matches=found==version,
                  architecture=architecture(), catalog=API+'/system/clients?download=true',
                  catalog_hash_algorithm=algorithm,catalog_hash=digest.lower(),bytes=size,
                  sha256=hashlib.sha256(executable.read_bytes()).hexdigest())
    write_json(folder / 'client-verification.json', result)
    return executable, found


def validate_forward_config(raw, port=8771):
    """Accept exactly one forwarder to our dedicated loopback MCP, no plugins."""
    try:
        if raw.lstrip().startswith('{'): raise ValueError()
        if '[[proxies]]' in raw:
            import tomllib
            data = tomllib.loads(raw)
            proxies = data.get('proxies',[])
            if len(proxies)!=1: raise ValueError()
            proxy = proxies[0]
            if (proxy.get('localIP')!='127.0.0.1' or proxy.get('localPort')!=port
                    or proxy.get('type') not in ('tcp','http') or proxy.get('plugin')): raise ValueError()
        else:
            parser = configparser.ConfigParser(interpolation=None,strict=True)
            parser.read_file(io.StringIO(raw))
            sections = [s for s in parser.sections() if s!='common']
            if len(sections)!=1 or 'common' not in parser: raise ValueError()
            proxy = parser[sections[0]]
            if (proxy.get('local_ip')!='127.0.0.1' or proxy.getint('local_port')!=port
                    or proxy.get('type') not in ('tcp','http') or any(k.startswith('plugin') for k in proxy)): raise ValueError()
    except Exception:
        raise SakuraError('Refused tunnel configuration: expected exactly one forwarder to 127.0.0.1:8771') from None
    return raw


def configure_tunnel(api, tunnel_id, version, folder, port=8771):
    if type(tunnel_id) is not int or tunnel_id <= 0: raise SakuraError('Invalid dedicated tunnel ID')
    tunnels = api.request('/tunnels')
    selected = [t for t in tunnels if t.get('id')==tunnel_id]
    if len(selected)!=1: raise SakuraError('Dedicated tunnel ID is not available in this Sakura account')
    tunnel = selected[0]
    if tunnel.get('type') not in ('tcp','http') or tunnel.get('status')!=0:
        raise SakuraError('Use a working TCP/HTTP tunnel with automatic HTTPS, not a raw HTTPS backend')
    extra = tunnel.get('extra','') or ''
    if not re.search(r'(?m)^\s*auto_https\s*=\s*auto\s*$', extra):
        raise SakuraError('Enable automatic HTTPS (auto) and bind a trusted-certificate subdomain in Sakura first')
    if tunnel.get('local_ip')!='127.0.0.1' or tunnel.get('local_port')!=port:
        # The user explicitly designated this dedicated tunnel for this project.
        api.request('/tunnel/edit', dict(id=tunnel_id,local_ip='127.0.0.1',local_port=port))
    raw = api.request('/tunnel/config',dict(query=str(tunnel_id),frpc=version),text=True)
    validate_forward_config(raw,port)
    path = Path(folder)/'frpc-private.ini'
    write_private(path,raw)
    return path
