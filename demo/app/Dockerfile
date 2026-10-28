FROM python:3.15-slim-bookworm

# Pin the base image digest before a release:
# docker inspect --format '{{index .RepoDigests 0}}' python:3.15-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv
COPY pyproject.toml uv.lock README.md LICENSE llms.txt ./
COPY docs/ai ./docs/ai
COPY src ./src
COPY demo ./demo
RUN pip install --no-cache-dir ".[server]"

RUN useradd --uid 65532 --no-create-home app
USER 65532
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "demo.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
