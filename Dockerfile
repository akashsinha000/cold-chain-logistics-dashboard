FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

WORKDIR /app

COPY requirements-offline.txt ./
RUN pip install --no-cache-dir -r requirements-offline.txt

COPY src ./src
COPY data ./data
COPY .streamlit ./.streamlit
COPY .env.example ./

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD-SHELL python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8501') + '/_stcore/health')"

CMD ["sh", "-c", "streamlit run src/ui.py --server.port ${PORT}"]