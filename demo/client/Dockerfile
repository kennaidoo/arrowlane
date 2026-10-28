FROM python:3.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv
COPY pyproject.toml uv.lock README.md LICENSE llms.txt ./
COPY docs/ai ./docs/ai
COPY src ./src
RUN pip install --no-cache-dir .
COPY demo/client/main.py /srv/client.py

RUN useradd --uid 65532 --no-create-home app
USER 65532
CMD ["python", "/srv/client.py"]
