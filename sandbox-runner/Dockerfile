FROM python:3.11-slim
WORKDIR /app

# docker-cli provides the `docker` client binary only (no dockerd/containerd/runc —
# those aren't needed since we never run a local daemon). It talks to docker-socket-proxy
# over DOCKER_HOST=tcp://... (set as an env var in docker-compose.yml), never the local
# socket. NOTE: the `docker.io` package on Debian trixie does NOT ship /usr/bin/docker
# (only dockerd/docker-proxy) — found during TI-B item 4 / foroba#120 E2E verification.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl docker-cli && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py main.py sandbox_docker.py ./

# Plan AU M-5/M-6: unprivileged. The host .workspaces bind mount must be chown'd to 10001.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --create-home --home-dir /home/app app \
 && mkdir -p /tmp/sandbox-workspaces && chown app:app /tmp/sandbox-workspaces \
 && chmod a+rX /app /app/*.py
USER app

EXPOSE 8090
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8090"]
