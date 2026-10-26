#!/usr/bin/env python3
"""Generate short-lived static HLS playlists from the encrypted migu-live core.

Required: MIGU_CLIENT_ID, MIGU_DEVICE_ID, MIGU_CORE_KEY when using migu_core.enc.
Optional login: MIGU_ACCOUNT_HEADERS_JSON (repository secret; JSON object incl. sign).
"""
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = Path(os.environ.get('OUT_DIR', str(ROOT / 'out')))
CHANNELS = json.loads((Path(__file__).parent / 'channels.json').read_text())


def load_core():
    import migu_core
    core = migu_core.load(force=True)
    if core not in sys.path:
        sys.path.insert(0, core)
    import migu_live
    return migu_live


def _absolute_uri(base, ref):
    from urllib.parse import urlsplit, urlunsplit
    resolved = urljoin(base, ref)
    dst, src = urlsplit(resolved), urlsplit(base)
    if not dst.query and src.query:
        resolved = urlunsplit((dst.scheme, dst.netloc, dst.path,
                               src.query, dst.fragment))
    return resolved


def absolute_playlist(sub_url, text):
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            out.append(line)
        elif stripped.startswith('#'):
            def repl(match):
                return 'URI="%s"' % _absolute_uri(sub_url, match.group(1))
            out.append(re.sub(r'URI="([^"]+)"', repl, line))
        else:
            out.append(_absolute_uri(sub_url, stripped))
    return '\n'.join(out) + '\n'


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.migu-', dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise


def main():
    if not os.environ.get('MIGU_CORE_KEY'):
        print('missing_core_key')
        return 2
    try:
        m = load_core()
        client_id, device_id = m._defaults()
        resolver = m.Resolver(client_id, device_id,
                              ttl=float(os.environ.get('MIGU_TTL', '3600')))
    except Exception as e:
        print('core_load_failed:', type(e).__name__)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    ok, failed = [], 0
    for channel in CHANNELS:
        cid, name = str(channel['id']), channel['name']
        try:
            sub, playlist = resolver.get(cid, force=True)
            text = absolute_playlist(sub, playlist)
            atomic_write(OUT / (cid + '.m3u8'), text)
            ok.append((cid, name))
            print('OK', cid)   # Never print signed URL or response body.
        except Exception as e:
            failed += 1
            stage = getattr(e, 'stage', 'upstream')
            code = str(getattr(e, 'code', type(e).__name__))
            code = re.sub(r'[^A-Za-z0-9_-]', '', code)[:40]
            print('ERR', cid, str(stage)[:24], code)
    if not ok:
        print('summary 0', len(CHANNELS), 'failed', failed, '- previous index retained')
        return 1
    lines = ['#EXTM3U']
    for cid, name in ok:
        lines.extend((f'#EXTINF:-1 tvg-id="{cid}" group-title="咪咕",{name}', cid + '.m3u8'))
    atomic_write(OUT / 'all.m3u', '\n'.join(lines) + '\n')
    atomic_write(OUT / 'index.html', '<meta charset="utf-8"><title>Migu HLS</title><ul>' +
                 ''.join(f'<li><a href="{cid}.m3u8">{name}</a></li>' for cid, name in ok) +
                 '</ul><p>generated UTC ' + time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) + '</p>')
    print('summary', len(ok), len(CHANNELS), 'failed', failed)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
