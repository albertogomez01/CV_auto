#!/bin/bash
set -e

echo "🚀 Iniciando Entorno de Empleo Autónomo (FastAPI + Streamlit)..."

# Trap SIGINT and SIGTERM to gracefully shut down background services
cleanup() {
    echo "🛑 Deteniendo servicios..."
    kill -TERM "$API_PID" "$STREAMLIT_PID" 2>/dev/null || true
    wait "$API_PID" "$STREAMLIT_PID" 2>/dev/null || true
    echo "✅ Servicios detenidos correctamente."
    exit 0
}

trap cleanup SIGINT SIGTERM

# 1. Start FastAPI Backend in background
echo "⚡ Iniciando FastAPI Backend en puerto 8000..."
uvicorn main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

# Wait for FastAPI health check
echo "⏳ Esperando a que el Backend FastAPI esté listo..."
until curl -s http://localhost:8000/health > /dev/null; do
    sleep 1
done
echo "✅ Backend FastAPI en ejecución (PID: $API_PID)."

# 2. Start Streamlit Dashboard in background
echo "📊 Iniciando Dashboard Streamlit en puerto 8501..."
streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true &
STREAMLIT_PID=$!
echo "✅ Dashboard Streamlit en ejecución (PID: $STREAMLIT_PID)."

# Wait for background processes to keep container alive 24/7
wait -n "$API_PID" "$STREAMLIT_PID"
