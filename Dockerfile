FROM python:3.12-alpine

LABEL org.opencontainers.image.title="migu-live" \
      org.opencontainers.image.description="Encrypted-core Migu playlist generator / gateway"

ENV PYTHONUNBUFFERED=1 \
    OUT_DIR=/out \
    MODE=files \
    INTERVAL=3600 \
    MIGU_QUALITY=compat \
    MIGU_ANDROID_TIMEOUT=8

WORKDIR /app
RUN apk add --no-cache tini \
 && pip install --no-cache-dir --disable-pip-version-check 'cryptography>=44,<47' \
 && addgroup -S -g 10001 migu && adduser -S -D -u 10001 -G migu migu \
 && mkdir -p /out && chown 10001:10001 /out

# Never copy plaintext core, account JSON, HAR, or source credentials into the image.
COPY migu_core.py migu_core.enc ./
COPY ci/gen_playlists.py /app/ci/gen_playlists.py
COPY ci/channels.json /app/ci/channels.json
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod 0555 /entrypoint.sh && chmod 0444 /app/migu_core.py /app/migu_core.enc /app/ci/gen_playlists.py /app/ci/channels.json

VOLUME ["/out"]
USER migu
ENTRYPOINT ["/sbin/tini", "--", "/entrypoint.sh"]
