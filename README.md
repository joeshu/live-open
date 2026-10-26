# Migu Live Deployment

This repository contains only the encrypted playback core and deployment wrappers. No plaintext signer source, account snapshot, HAR, or raw playback URLs are committed.

## Required GitHub Actions secrets

- `MIGU_CORE_KEY`: same strong passphrase used to create `migu_core.enc` (required).
- Optional `MIGU_USER_ID` and `MIGU_USER_TOKEN`: can override the account values after the current session snapshot is imported.
- Optional `MIGU_ACCOUNT_HEADERS_JSON`: the current account header snapshot, including `UserInfo` and session `sign`. User ID/token alone cannot authenticate; the signer and UserInfo are reused from this snapshot. After importing a fresh HAR locally, the helper can upload UserId, UserToken, and the matching complete header snapshot without printing values; the snapshot preserves UserInfo/sign for the same session.
- Optional `MIGU_CLIENT_ID`, `MIGU_DEVICE_ID`: if omitted, the encrypted core uses its packaged defaults.

The encrypted bytecode is compiled for CPython 3.12; both workflows pin Python 3.12.

## Actions + Pages

The hourly workflow generates HLS playlists. Pages publishing is intentionally disabled by default. Set the repository variable `MIGU_PAGES_PUBLIC=true` only if you accept that Pages exposes short-lived signed playback URLs publicly. Do not enable Pages for private streams unless this exposure is acceptable.

## Docker / GHCR

Publish on a `migu-v*` tag or via the manual `publish-migu-docker` workflow. Keep the GHCR package private. On a server, inject the secrets via a secret manager and mount an output directory:

```sh
mkdir -p /srv/migu
sudo chown 10001:10001 /srv/migu
docker pull ghcr.io/OWNER/REPO/migu-live:TAG
docker run -d --name migu-playlist --restart unless-stopped \
  -e MIGU_CORE_KEY -e MIGU_CLIENT_ID -e MIGU_DEVICE_ID \
  -e MIGU_ACCOUNT_HEADERS_JSON -e MODE=files -e INTERVAL=3600 \
  -v /srv/migu:/out ghcr.io/OWNER/REPO/migu-live:TAG
```

Output playlists contain short-lived upstream URLs. Keep `/srv/migu` private. `MODE=serve` runs the encrypted local gateway instead of writing static files.

## Updating the core

The source workspace is kept separate from this deployment-only repository. On a trusted Python 3.12 machine with the same `MIGU_CORE_KEY`, run `python3.12 ci/pack.py` in the full source project, then replace `migu_core.enc` here. Do not copy source files or `.migu-account.json` into this repo.

`migu_core.enc` uses AES-256-GCM with PBKDF2-HMAC-SHA256 (200,000 rounds). Core Python modules are bytecode inside the encrypted envelope; bytecode is reversible, so key secrecy is the actual protection. Runtime decryption occurs in a temporary directory and cannot protect against a host administrator who controls the running container.


`all.m3u` is generated in IPTV M3U format: every `#EXTINF` is followed by the absolute signed Migu HLS playlist URL (not a Pages wrapper URI). The static channel `.m3u8` files are diagnostic mirrors. The generator uses the encrypted core catalog; channels blocked by `COPYRIGHT_SHIELD_INVALID` are skipped, while transient failures abort publication and preserve the previous Pages snapshot.

GitHub-hosted runner was tested twice and could not reach Migu APIs (`Network is unreachable`). To avoid burning Actions minutes on hourly failures, cron is currently disabled; `workflow_dispatch` is retained with a fast network preflight. Use direct local/server generation until a runner with Migu network access is available.
