FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend

# Runtime lib required by opencv-python-headless (libGL is NOT needed for headless build).
RUN apt-get update \
    && apt-get install --no-install-recommends -y libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts

# SQLite file lives on a mounted volume in compose (see DATABASE_URL).
RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
