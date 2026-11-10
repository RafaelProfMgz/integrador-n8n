FROM python:3.12-slim
WORKDIR /app
RUN groupadd --gid 1000 editorial && useradd --uid 1000 --gid editorial --no-create-home editorial && mkdir /data && chown editorial:editorial /data
COPY app.py image_agent.py community.py comments_api.py response_engine.py /app/
USER 1000:1000
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "/app/app.py"]
