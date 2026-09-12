FROM python:3.12.7-slim-bookworm
ARG FFMPEG_VERSION=7:5.1.7-0+deb12u1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg=${FFMPEG_VERSION} libmagic1=1:5.44-3 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.lock
COPY . .
RUN useradd -r -u 10001 kira && mkdir -p /data/projects && chown -R kira:kira /data/projects /app
USER kira
CMD ["uvicorn","app.api.main:app","--host","0.0.0.0","--port","8000"]
