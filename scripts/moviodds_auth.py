"""Provider-scoped credentials for MoviOdds downloads. Secrets never enter a URL."""
import os
import re
from urllib.parse import urlsplit

CREDENTIAL_TARGET = 'IlMargine/MoviOdds'
ALLOWED_PATHS = {'/odds', '/quotes'}

def windows_credential():
    if os.name != 'nt':
        return None
    import ctypes as ct
    from ctypes import wintypes as wt
    class Credential(ct.Structure):
        _fields_ = [('Flags',wt.DWORD),('Type',wt.DWORD),('TargetName',wt.LPWSTR),('Comment',wt.LPWSTR),
                    ('LastWritten',wt.FILETIME),('CredentialBlobSize',wt.DWORD),('CredentialBlob',ct.c_void_p),
                    ('Persist',wt.DWORD),('AttributeCount',wt.DWORD),('Attributes',ct.c_void_p),
                    ('TargetAlias',wt.LPWSTR),('UserName',wt.LPWSTR)]
    adv = ct.WinDLL('Advapi32',use_last_error=True)
    adv.CredReadW.argtypes=[wt.LPCWSTR,wt.DWORD,wt.DWORD,ct.POINTER(ct.POINTER(Credential))]
    adv.CredReadW.restype=wt.BOOL
    adv.CredFree.argtypes=[ct.c_void_p]
    ptr=ct.POINTER(Credential)()
    if not adv.CredReadW(CREDENTIAL_TARGET,1,0,ct.byref(ptr)):
        return None
    try:
        return ct.string_at(ptr.contents.CredentialBlob,ptr.contents.CredentialBlobSize).decode('utf-16-le') or None
    finally:
        adv.CredFree(ptr)

class AccessFailure(ValueError):
    def __init__(self,reason,status):
        super().__init__(reason)
        self.reason=reason
        self.status=status

def request_headers(url, params):
    parsed=urlsplit(url)
    if (parsed.scheme!='https' or parsed.netloc!='moviodds.com' or parsed.path not in ALLOWED_PATHS
            or parsed.query or parsed.fragment):
        raise ValueError('Unrecognised MoviOdds destination')
    base={'Accept-Encoding':'gzip','User-Agent':'IlMargineResearch/1.0'}
    if parsed.path == '/odds':
        supported = params.get('sport') in ('soccer', 'tennis') and params.get('site') in (None, 'com', 'com.au')
    else:
        supported = params.get('site') == 'com' and re.fullmatch(r'[1-9][0-9]*', str(params.get('fi', '')))
    if not supported:
        raise ValueError('Unrecognised MoviOdds request')
    key=os.environ.get('MOVIODDS_API_KEY') or windows_credential()
    if key:
        base['X-API-Key']=key
    return base

def check_http_status(response,authenticated):
    status=getattr(response,'status_code',200)
    if status==401:
        raise AccessFailure('MOVIODDS_KEY_REJECTED' if authenticated else 'MOVIODDS_KEY_REQUIRED',status)
    if status==403:
        raise AccessFailure('MOVIODDS_ACCESS_DENIED',status)
    if status==429:
        raise AccessFailure('MOVIODDS_RATE_LIMITED',status)
    if 300<=status<400:
        raise AccessFailure('MOVIODDS_REDIRECT_REFUSED',status)
    if status>=400:
        raise AccessFailure('MOVIODDS_HTTP_'+str(status),status)
