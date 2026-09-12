FROM python:3.12.7-slim-bookworm
# Debian security repositories replace package revisions over time. Pinning an old
# revision makes otherwise reproducible rebuilds fail once that revision is
# removed. The immutable base image controls the OS release; apt selects the
# currently supported Bookworm security revision of these runtime packages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libmagic1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.lock
COPY . .
RUN useradd -r -u 10001 kira && mkdir -p /data/projects && chown -R kira:kira /data/projects /app
USER kira
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
