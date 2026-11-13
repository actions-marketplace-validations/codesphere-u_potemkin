FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r potemkin && useradd -r -g potemkin -m potemkin

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY skills/potemkin/scripts/potemkin.py skills/potemkin/scripts/potemkin.py

RUN pip install --no-cache-dir --no-deps .

USER potemkin
WORKDIR /workspace

ENTRYPOINT ["potemkin"]
CMD ["."]
