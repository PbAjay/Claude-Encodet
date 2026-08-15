FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

WORKDIR /bot

# mediainfo for the /getcode mediainfo report; curl/xz to fetch a static ffmpeg
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        mediainfo curl xz-utils ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Pull the latest static ffmpeg build (newer than what Debian bookworm ships)
# for the correct architecture (amd64 or arm64 — Oracle's Always Free Ampere
# VMs are arm64).
ARG TARGETARCH
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) FF_ARCH=amd64 ;; \
        arm64) FF_ARCH=arm64 ;; \
        *) echo "Unsupported arch: ${TARGETARCH}" && exit 1 ;; \
    esac; \
    curl -fsSL "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-${FF_ARCH}-static.tar.xz" \
        -o /tmp/ffmpeg.tar.xz && \
    tar -xf /tmp/ffmpeg.tar.xz -C /tmp && \
    mv /tmp/ffmpeg-*-static/ffmpeg /tmp/ffmpeg-*-static/ffprobe /usr/local/bin/ && \
    rm -rf /tmp/ffmpeg*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "-m", "bot"]
