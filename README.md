# Migu Live Deployment

This repository contains only the encrypted playback core and deployment wrappers. No plaintext signer source, account snapshot, HAR, or raw playback URLs are committed.

## Required GitHub Actions secrets

- `MIGU_CORE_KEY`: same strong passphrase used to create `migu_core.enc` (required).
- Optional overrides `MIGU_CLIENT_ID`, `MIGU_DEVICE_ID`: if omitted, the encrypted core uses its packaged defaults.
- Optional `MIGU_ACCOUNT_HEADERS_JSON`: JSON object containing the current App request-header snapshot, including the session-level `sign` header. Refresh after a new logged-in capture; never put it in a file committed to Git.

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
