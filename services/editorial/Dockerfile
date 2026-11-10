FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN groupadd --gid 1000 editorial && useradd --uid 1000 --gid editorial --no-create-home editorial && mkdir /data && chown editorial:editorial /data
COPY *.py media-panel.html /app/
USER 1000:1000
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "/app/app.py"]
