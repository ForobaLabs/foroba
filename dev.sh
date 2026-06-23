#!/usr/bin/env bash
# Start Foroba: Jeli backend (8002) + Vite frontend (5175)
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
  echo ""
  echo "Stopping Foroba services..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  echo "Done."
}
trap cleanup EXIT INT TERM

echo "Starting Foroba Jeli backend on port 8002..."
cd "$ROOT/backend"
.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8002 --reload &
BACKEND_PID=$!

echo "Starting Foroba frontend on port 5175..."
cd "$ROOT"
pnpm run dev &
FRONTEND_PID=$!

echo ""
echo "Foroba running:"
echo "  Frontend → http://localhost:5175"
echo "  Jeli API → http://localhost:8002"
echo ""
echo "Press Ctrl+C to stop."
wait
