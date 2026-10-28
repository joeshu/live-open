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
PUBLIC_BASE = os.environ.get('PUBLIC_BASE', 'https://joeshu.github.io/live-open/').rstrip('/') + '/'


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
        # A static playlist has no adaptive codec fallback; default to H.264 for wider player compatibility.
        m.QUALITY_MODE = os.environ.get('MIGU_QUALITY', 'compat')
        channels = m.load_channels()
        if not channels:
            raise RuntimeError('empty channel catalog')
        client_id, device_id = m._defaults()
        resolver = m.Resolver(client_id, device_id,
                              ttl=float(os.environ.get('MIGU_TTL', '3600')))
        current_cid = [None]
        master_urls = {}
        original_http_get_final = m.http_get_final
        def capture_master(url, *args, **kwargs):
            response = original_http_get_final(url, *args, **kwargs)
            if current_cid[0] and response[0] == 200:
                # Keep the original GSLB entry URL for IPTV clients. Do not publish
                # the redirected edge host (often :8080), which many players cannot reach.
                master_urls[current_cid[0]] = url
            return response
        m.http_get_final = capture_master
    except Exception as e:
        print('core_load_failed:', type(e).__name__)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    ok, failed = {}, {}
    for channel in channels:
        cid, name = str(channel['id']), channel['name']
        current_cid[0] = cid
        for attempt in range(1, 4):
            try:
                sub, playlist = resolver.get(cid, force=True)
                master = master_urls.get(cid)
                if not master:
                    raise RuntimeError('missing original master URL')
                text = absolute_playlist(sub, playlist)
                atomic_write(OUT / (cid + '.m3u8'), text)
                ok[cid] = (name, master)
                print('OK', cid)
                break
            except Exception as e:
                detail = str(e)
                blocked = 'COPYRIGHT_SHIELD_INVALID' in detail
                stage = getattr(e, 'stage', 'upstream')
                code = 'COPYRIGHT_SHIELD_INVALID' if blocked else str(getattr(e, 'code', type(e).__name__))
                code = re.sub(r'[^A-Za-z0-9_-]', '', code)[:40]
                failed[cid] = (name, code)
                if attempt < 3 and not blocked:
                    resolver.states.pop(cid, None)
                    resolver.cache.pop(cid, None)
                    master_urls.pop(cid, None)
                    time.sleep(attempt)
                    continue
                print('SKIP' if blocked else 'ERR', cid, str(stage)[:24], code)
                break

    lines = ['#EXTM3U']
    index_items = []
    for channel in channels:
        cid, name = str(channel['id']), channel['name']
        safe_name = name.replace('"', '&quot;')
        if cid in ok:
            lines.extend((f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{safe_name}" group-title="咪咕",{safe_name}', ok[cid][1]))
            index_items.append(f'<li><a href="{cid}.m3u8">{name}</a></li>')
        else:
            stale = OUT / (cid + '.m3u8')
            try:
                stale.unlink()
            except FileNotFoundError:
                pass
            reason = failed.get(cid, ('', 'UPSTREAM_ERROR'))[1]
            label = f'{safe_name} [本轮无可用新链接: {reason}]'
            lines.extend((f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{label}" group-title="咪咕",{label}', f'unavailable://{cid}'))
            index_items.append(f'<li>{name} — unavailable ({reason})</li>')
    atomic_write(OUT / 'all.m3u', '\n'.join(lines) + '\n')
    atomic_write(OUT / 'index.html', '<meta charset="utf-8"><title>Migu HLS</title><ul>' +
                 ''.join(index_items) +
                 '</ul><p>generated UTC ' + time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) + '</p>')
    print('summary', len(ok), len(channels), 'unavailable', len(failed),
          '- all catalog entries published; failed channels have no stale URLs')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
