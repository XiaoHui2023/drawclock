#!/usr/bin/env bash
# CI helper: pack drawclock inside Ubuntu 16.04 (glibc 2.23 baseline).
# Invoked from .github/workflows/release.yml via docker run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

rm -rf .venv build dist

export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=5 update
apt-get install -o Acquire::Retries=5 -y --no-install-recommends ca-certificates wget bzip2 binutils patchelf build-essential musl-tools

MINICONDA=Miniconda3-py310_23.5.2-0-Linux-x86_64.sh
MINICONDA_URL="https://repo.anaconda.com/miniconda/${MINICONDA}"
for attempt in 1 2 3 4 5; do
  wget --tries=1 -O "/tmp/${MINICONDA}" "$MINICONDA_URL" && break
  if [[ "$attempt" == "5" ]]; then
    echo "ERROR: failed to download Miniconda" >&2
    exit 1
  fi
  sleep 5
done

bash "/tmp/${MINICONDA}" -b -p /opt/conda
export PATH="/opt/conda/bin:$PATH"

python -m venv .venv
bash tools/pack.sh
