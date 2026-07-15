FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ARG EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
ENV EMBEDDING_MODEL=$EMBEDDING_MODEL EMBEDDING_CACHE_DIR=/models/fastembed

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "import os; from fastembed import TextEmbedding; TextEmbedding(model_name=os.environ['EMBEDDING_MODEL'], cache_dir=os.environ['EMBEDDING_CACHE_DIR'])"

COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
