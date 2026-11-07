"""Renew publisher OAuth without allowing CLI failures to erase saved access.

Secrets stay in process memory and the existing Vercel credential store. The
CLI receives only a child-process environment token, so its skipWrite path is
used. This does not create a second login or change project/team permissions.
"""
from contextlib import contextmanager
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

# Public OAuth client identity from the installed official Vercel CLI (54.4.1).
CLIENT_ID = 'cl_HYyOPBNtFMfHhaUn9L4QPfTZz6TP47bp'
TOKEN_ENDPOINT = 'https://api.vercel.com/login/oauth/token'
RENEW_BEFORE_SECONDS = 600


class PublicationAuthRequired(RuntimeError):
    pass


class PublicationAuthUnavailable(RuntimeError):
    pass


def cli_store(executable, env):
    executable = shutil.which(str(executable)) or str(executable)
    module = Path(executable).resolve().parent / 'node_modules/vercel/node_modules/@vercel/cli-config/dist/cli-config.js'
    node = shutil.which('node')
    if not node or not module.is_file():
        raise PublicationAuthUnavailable('Cannot resolve the installed Vercel credential store; no login started.')
    # Only the path crosses stdout, never an auth object or token.
    probe = "const c=require(process.argv[1]);process.stdout.write(JSON.stringify(c.getAuthConfigFilePath(c.getGlobalPathConfig())));"
    try:
        result = subprocess.run([node, '-e', probe, str(module)], env=env,
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        path = Path(json.loads(result.stdout))
        if result.returncode or not path.is_absolute() or path.name != 'auth.json':
            raise ValueError()
    except Exception:
        raise PublicationAuthUnavailable('Cannot resolve the saved Vercel login; credentials were not changed.') from None
    return path, node, module


@contextmanager
def renewal_lock(path, timeout=20):
    """An OS-owned mutex: crashes release it, and waiters reread rotated tokens."""
    if os.name != 'nt':
        # This publisher is installed on Windows. Fail closed elsewhere rather
        # than accidentally rotate the same refresh token without a lock.
        raise PublicationAuthUnavailable('Publisher renewal requires the Windows credential mutex.')
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    name = 'Local\\IlMargine.VercelRenewal.' + hashlib.sha256(str(path.resolve()).casefold().encode()).hexdigest()[:24]
    handle = kernel.CreateMutexW(None, False, name)
    if not handle:
        raise PublicationAuthUnavailable('Cannot lock saved Vercel access; no renewal attempted.')
    acquired = False
    try:
        result = kernel.WaitForSingleObject(handle, int(timeout * 1000))
        acquired = result in (0, 0x80)  # Signalled or abandoned owner.
        if not acquired:
            raise PublicationAuthUnavailable('Another publisher is renewing Vercel access; retry publication only.')
        yield
    finally:
        if acquired:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


def read_auth(path):
    try:
        with path.open(encoding='utf-8-sig') as stream:
            raw = stream.read(65537)
        auth = json.loads(raw) if len(raw) <= 65536 else None
        if not isinstance(auth, dict):
            raise ValueError()
        return auth
    except Exception:
        raise PublicationAuthRequired('Saved Vercel access is missing or unreadable. Sign in deliberately; no hidden login was started.') from None


def fresh(auth, now):
    if not isinstance(auth.get('token'), str) or not auth['token']:
        return False
    # Legacy personal tokens have no expiry field; preserve existing support.
    if auth.get('expiresAt') is None:
        return True
    expiry = auth['expiresAt']
    return isinstance(expiry, (int, float)) and math.isfinite(expiry) and expiry > now + RENEW_BEFORE_SECONDS


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # Never forward a renewal credential away from its provider.


def exchange(refresh_token):
    body = urllib.parse.urlencode({'client_id': CLIENT_ID, 'grant_type': 'refresh_token',
                                  'refresh_token': refresh_token}).encode()
    request = urllib.request.Request(TOKEN_ENDPOINT, body, method='POST', headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'IlMargine-PublisherRenewal/1.0'})
    opener = urllib.request.build_opener(NoRedirect())
    # One bounded retry for transport/429/5xx failure. Never retry invalid_grant.
    for attempt in range(2):
        try:
            with opener.open(request, timeout=8) as response:
                raw = response.read(16385)
            data = json.loads(raw) if len(raw) <= 16384 else None
            if (not isinstance(data, dict) or not isinstance(data.get('access_token'), str)
                    or not data['access_token'] or data.get('token_type') != 'Bearer'
                    or not isinstance(data.get('expires_in'), (int, float))
                    or not math.isfinite(data['expires_in']) or data['expires_in'] <= RENEW_BEFORE_SECONDS
                    or ('refresh_token' in data and
                        (not isinstance(data['refresh_token'], str) or not data['refresh_token']))):
                raise ValueError()
            return data
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()  # Never include provider bodies/headers in logs.
            if status in (400, 401, 403):
                raise PublicationAuthRequired('Vercel rejected renewal of the saved login. Credentials were retained; deliberate sign-in is required.') from None
            transient = status == 429 or status >= 500
        except (urllib.error.URLError, TimeoutError, OSError):
            transient = True
        except (ValueError, TypeError):
            transient = False
        if not transient or attempt:
            raise PublicationAuthUnavailable('Vercel token renewal was unavailable. Saved credentials were retained; retry publication only.') from None
        time.sleep(1)


def save_auth(path, auth, node, module, env):
    # Use the provider's existing credential-store writer, including its atomic
    # replacement and permissions. No independent plaintext backup/export.
    writer = "const fs=require('node:fs');try{const c=require(process.argv[1]);c.writeAuthConfigFile(process.argv[2],JSON.parse(fs.readFileSync(0,'utf8')));process.stdout.write('saved');}catch{process.exitCode=1;}"
    for attempt in range(2):
        try:
            result = subprocess.run([node, '-e', writer, str(module), str(path)],
                input=json.dumps(auth), env=env, capture_output=True, text=True,
                timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if (result.returncode == 0 and result.stdout == 'saved'
                    and read_auth(path) == auth):
                return
        except Exception:
            pass
        if not attempt:
            time.sleep(0.25)
    raise PublicationAuthUnavailable('Vercel renewed access but credential persistence could not be verified. Publication stopped; review the saved login.')


def prepare_environment(executable, env, *, force_refresh=False, metadata=None):
    result = dict(env)
    if result.get('VERCEL_TOKEN'):
        if force_refresh:
            raise PublicationAuthUnavailable('Cannot renew an explicit environment token using saved OAuth credentials.')
        if metadata is not None:
            metadata.update(source='environment', renewed=False)
        return result
    path, node, module = cli_store(executable, result)
    with renewal_lock(path):
        auth = read_auth(path)
        renewed = False
        if force_refresh or not fresh(auth, time.time()):
            if not isinstance(auth.get('refreshToken'), str) or not auth['refreshToken']:
                raise PublicationAuthRequired('Saved Vercel access cannot renew. Sign in deliberately; credentials were retained.')
            tokens = exchange(auth['refreshToken'])
            latest = read_auth(path)
            if latest != auth:
                # An unrelated interactive CLI login does not use our mutex.
                # Never overwrite its newer credentials with this exchange.
                if not fresh(latest, time.time()):
                    raise PublicationAuthUnavailable('Vercel login changed during renewal; no newer credentials were overwritten.')
                auth = latest
            else:
                auth = {**auth, 'token': tokens['access_token'],
                        'expiresAt': int(time.time()) + int(tokens['expires_in']),
                        'refreshToken': tokens.get('refresh_token', auth['refreshToken'])}
                auth.pop('skipWrite', None)
                auth.pop('tokenSource', None)
                save_auth(path, auth, node, module, result)
                renewed = True
        result['VERCEL_TOKEN'] = auth['token']
        if metadata is not None:
            metadata.update(source='saved_oauth', renewed=renewed,
                            renewable=bool(auth.get('refreshToken')), expiresAt=auth.get('expiresAt'))
    return result
