#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODEL="${1:-${GENESIS_LLM_MODEL:-mistral-nemo:latest}}"
MODEL_SLUG="$(printf '%s' "$MODEL" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/_/g')"
OLLAMA_BIN="${OLLAMA_BIN:-/Volumes/Stratos_Tools/homebrew/bin/ollama}"

case "$MODEL" in
  "qwen3.5:27b")
    export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
    export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-15m}"
    ;;
  "gemma3:4b")
    export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11435}"
    export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-4m}"
    ;;
  "mistral-nemo:latest")
    export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11436}"
    export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-8m}"
    ;;
  *)
    export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
    export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-5m}"
    ;;
esac

export OLLAMA_MAX_LOADED_MODELS="${OLLAMA_MAX_LOADED_MODELS:-1}"
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-1}"
export OLLAMA_MAX_QUEUE="${OLLAMA_MAX_QUEUE:-1}"
export OLLAMA_NO_CLOUD="${OLLAMA_NO_CLOUD:-1}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-/Volumes/Stratos_Tools/models}"

RUNTIME_ROOT="$ROOT/outputs/_llm/runtimes/$MODEL_SLUG"
PID_FILE="$RUNTIME_ROOT/ollama.pid"
LOG_FILE="$RUNTIME_ROOT/ollama.log"
mkdir -p "$RUNTIME_ROOT"

if [ ! -x "$OLLAMA_BIN" ]; then
  echo "Ollama binary not executable: $OLLAMA_BIN" >&2
  exit 1
fi

if "$OLLAMA_BIN" list >/dev/null 2>&1; then
  PID="$("$OLLAMA_BIN" list >/dev/null 2>&1; lsof -nP -iTCP:"${OLLAMA_HOST##*:}" -sTCP:LISTEN -t 2>/dev/null | head -n 1 || true)"
  if [ -n "$PID" ]; then
    echo "$PID" >"$PID_FILE"
  fi
  echo "Runtime already live for $MODEL on $OLLAMA_HOST"
  echo "PID: ${PID:-unknown}"
  echo "Log: $LOG_FILE"
  exit 0
fi

nohup "$OLLAMA_BIN" serve >>"$LOG_FILE" 2>&1 </dev/null &
PID=$!
echo "$PID" >"$PID_FILE"
disown "$PID" 2>/dev/null || true

for _ in $(seq 1 12); do
  sleep 1
  if "$OLLAMA_BIN" list >/dev/null 2>&1; then
    echo "Runtime live for $MODEL on $OLLAMA_HOST"
    echo "PID: $PID"
    echo "Log: $LOG_FILE"
    exit 0
  fi
done

echo "Failed to start runtime for $MODEL on $OLLAMA_HOST" >&2
echo "Log: $LOG_FILE" >&2
exit 1
