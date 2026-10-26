#!/bin/sh
# Container runtime never prints secrets or signed media URLs.
set -eu

: "${MODE:=files}"            # files | serve
: "${INTERVAL:=3600}"        # URLs are short-lived; refresh hourly by default
: "${OUT_DIR:=/out}"
: "${PORT:=8765}"
: "${MIGU_QUALITY:=auto}"

: "${MIGU_CORE_KEY:?Set MIGU_CORE_KEY (same passphrase used by ci/pack.py)}"

mkdir -p "$OUT_DIR"

if [ "$MODE" = "serve" ]; then
    exec python3 /app/migu_core.py run migu_live --serve "$PORT" --lan
fi

if [ "$MODE" != "files" ]; then
    echo "MODE must be files or serve" >&2
    exit 2
fi

while :; do
    echo "[$(date -u +%FT%TZ)] generating playlists"
    if python3 /app/ci/gen_playlists.py; then
        echo "[$(date -u +%FT%TZ)] generation complete"
    else
        echo "[$(date -u +%FT%TZ)] generation failed; previous files retained"
    fi
    echo "[$(date -u +%FT%TZ)] next refresh in ${INTERVAL}s"
    sleep "$INTERVAL"
done
