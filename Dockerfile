FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libsqlite3-dev \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

# Запускаем через waitress
CMD ["waitress-serve", "--host=0.0.0.0", "--port=8080", "bot:app"]
