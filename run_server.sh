#!/bin/bash
# Start the RAG API server

cd "$(dirname "$0")" || exit 1

echo "🚀 Starting RAG API Server..."
echo "📍 Working directory: $(pwd)"

# Use nohup to keep process running even if terminal closes
nohup ./.venv/bin/python -m uvicorn src.api.app:app \
    --host 127.0.0.1 \
    --port 8000 \
    --log-level info > server.log 2>&1 &

SERVER_PID=$!
echo "✅ Server started with PID: $SERVER_PID"
echo "📊 Logs: tail -f server.log"
echo "🌐 API: http://127.0.0.1:8000/docs"
