#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found. Install Docker Desktop."
  exit 1
fi

if [[ -z "${1:-}" ]]; then
  echo "Usage: $0 <timesketch-dir>"
  echo "Hint: clone https://github.com/google/timesketch and run from its directory"
  exit 1
fi

cd "$1"
if [[ ! -f docker-compose.yml ]]; then
  echo "docker-compose.yml not found in $1"
  exit 1
fi

docker compose up -d

echo "Timesketch should be available on its configured port."
