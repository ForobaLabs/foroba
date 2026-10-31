FROM python:3.12-slim
WORKDIR /app

# sqlcipher3 compiles against libsqlcipher; keep only the runtime .so in the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libsqlcipher-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && python -m spacy download it_core_news_lg \
 && apt-get purge -y gcc && apt-get install -y --no-install-recommends libsqlcipher1 \
 && rm -rf /var/lib/apt/lists/*

COPY *.py ./
COPY masking ./masking
COPY providers ./providers

# Plan AU: unprivileged uid 10001; the /data volume must be chown'd to 10001 on the host.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --create-home --home-dir /home/app app \
 && mkdir -p /data && chown app:app /data \
 && chmod -R a+rX /app
USER app

EXPOSE 8090
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8090"]
