"""Telegram relay: retry only proven non-delivery; save per-message acknowledgements."""
import base64
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import socket
import ssl
import time
import urllib.request
import urllib.error
import zipfile


def digest(messages):
    return hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest()


def save(path, receipt):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    tmp.replace(path)


def deliver(messages, token, chat_id, path, previous=None,
            connection=http.client.HTTPSConnection, sleep=time.sleep):
    if not isinstance(messages, list) or not messages or any(
        not isinstance(m, str) or not m.strip() or len(m.encode('utf-16-le')) // 2 > 4096 for m in messages
    ):
        raise ValueError('Invalid message batch')
    receipt = previous or {'payload_sha256': digest(messages), 'messages': [], 'status': 'PENDING'}
    if receipt.get('payload_sha256') != digest(messages):
        raise ValueError('Receipt belongs to a different payload')
    acknowledged = receipt.get('messages', [])
    for i, item in enumerate(acknowledged):
        if item.get('index') != i or not item.get('message_id'):
            raise ValueError('Invalid acknowledgement sequence')
    if len(acknowledged) > len(messages):
        raise ValueError('Invalid acknowledgement count')
    if receipt.get('status') in {'UNKNOWN_DELIVERY', 'REJECTED'}:
        raise RuntimeError('Previous delivery needs reconciliation; automatic resend blocked')
    save(path, receipt)
    for index in range(len(acknowledged), len(messages)):
        body = json.dumps({'chat_id': chat_id, 'text': messages[index],
                           'disable_web_page_preview': True}).encode()
        for attempt in range(3):
            conn = connection('api.telegram.org', timeout=20)
            try:
                # Explicitly complete DNS/TCP/TLS before any HTTP request bytes.
                conn.connect()
            except ssl.SSLCertVerificationError:
                conn.close()
                receipt.update(status='REJECTED', failed_index=index, reason='TLS_CERTIFICATE')
                save(path, receipt)
                raise RuntimeError('Telegram certificate validation failed') from None
            except (OSError, TimeoutError, socket.timeout):
                conn.close()
                receipt.update(status='RETRYABLE_NOT_SENT', failed_index=index,
                               reason='CONNECT_FAILED_BEFORE_REQUEST', attempts=attempt + 1)
                save(path, receipt)
                if attempt < 2:
                    sleep(2 * (attempt + 1))
                    continue
                raise RuntimeError('Telegram connection failed before sending; safe to resume') from None
            # Persist uncertainty BEFORE transmission, including a runner interruption.
            receipt.update(status='UNKNOWN_DELIVERY', failed_index=index, reason='REQUEST_IN_FLIGHT')
            save(path, receipt)
            try:
                conn.request('POST', '/bot' + token + '/sendMessage', body,
                             {'Content-Type': 'application/json'})
                response = conn.getresponse()
                status = response.status
                data = json.loads(response.read())
            except Exception:
                raise RuntimeError('Telegram response unknown; automatic resend blocked') from None
            finally:
                conn.close()
            if status == 200 and data.get('ok') is True and isinstance(data.get('result', {}).get('message_id'), int):
                acknowledged.append({'index': index, 'message_id': data['result']['message_id']})
                receipt.update(status='PENDING', messages=acknowledged)
                receipt.pop('failed_index', None)
                receipt.pop('reason', None)
                save(path, receipt)
                break
            if status == 429 and data.get('ok') is False:
                delay = data.get('parameters', {}).get('retry_after', 1)
                receipt.update(status='RETRYABLE_NOT_SENT', reason='RATE_LIMIT_REJECTED')
                save(path, receipt)
                if attempt < 2 and isinstance(delay, (int, float)) and 0 <= delay <= 20:
                    sleep(delay + 1)
                    continue
                raise RuntimeError('Telegram explicitly rate-limited the unsent message')
            receipt.update(status='REJECTED' if 400 <= status < 500 else 'UNKNOWN_DELIVERY',
                           reason='TELEGRAM_HTTP_' + str(status))
            save(path, receipt)
            raise RuntimeError('Telegram delivery rejected or ambiguous; see receipt')
    receipt['status'] = 'DELIVERED'
    save(path, receipt)
    return receipt


def previous_attempt_receipt(messages):
    """A workflow rerun resumes acknowledged chunks instead of replaying the batch."""
    attempt = int(os.environ.get('GITHUB_RUN_ATTEMPT', '1'))
    if attempt <= 1:
        return None
    repo, run = os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_RUN_ID']
    token = os.environ['GH_TOKEN']
    def get(url):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token,
                                                  'Accept': 'application/vnd.github+json'})
        try:
            with urllib.request.build_opener(NoRedirect).open(req, timeout=20) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (301, 302, 303, 307, 308):
                raise RuntimeError('Cannot read previous delivery receipt') from None
            location = exc.headers.get('Location', '')
            if not location.startswith('https://'):
                raise RuntimeError('Unsafe artifact redirect')
            # Signed artifact download URL gets NO GitHub Authorization header.
            with urllib.request.urlopen(location, timeout=20) as response:
                return response.read()
    artifacts = json.loads(get(f'https://api.github.com/repos/{repo}/actions/runs/{run}/artifacts?per_page=100'))['artifacts']
    name = 'tennis-delivery-' + run + '-' + str(attempt - 1)
    found = [a for a in artifacts if a['name'] == name and not a['expired']]
    if len(found) != 1:
        raise RuntimeError('Previous delivery receipt unavailable; refusing blind workflow replay')
    raw = get(f"https://api.github.com/repos/{repo}/actions/artifacts/{found[0]['id']}/zip")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        receipt = json.loads(archive.read('telegram-delivery-receipt.json'))
    if receipt.get('payload_sha256') != digest(messages):
        raise ValueError('Previous receipt payload mismatch')
    return receipt


def main():
    messages = json.loads(base64.b64decode(os.environ['DIGEST_PAYLOAD_B64'], validate=True))
    token = os.environ.get('OPS_ALERT_TELEGRAM_BOT_TOKEN', '').strip()
    chat = os.environ.get('OPS_ALERT_TELEGRAM_CHAT_ID', '').strip()
    if not token or not chat:
        raise SystemExit('Missing Telegram credentials')
    receipt = deliver(messages, token, chat, 'telegram-delivery-receipt.json', previous_attempt_receipt(messages))
    print(f"Telegram acknowledged {len(receipt['messages'])} message(s); delivery verified.")


if __name__ == '__main__':
    main()
