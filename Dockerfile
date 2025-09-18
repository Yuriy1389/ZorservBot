# Используем стабильный Python 3.11
FROM python:3.11-slim

# Устанавливаем зависимости системы (sqlite, tzdata и др.)
RUN apt-get update && apt-get install -y \
    build-essential \
    libsqlite3-dev \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Задаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Указываем переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Открываем порт
EXPOSE 8080

# Запускаем бота
CMD ["python", "bot.py"]
