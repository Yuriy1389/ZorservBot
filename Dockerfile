FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Копируем все папки
COPY . .

# Создаем необходимые папки если их нет
RUN mkdir -p media user_media

CMD ["python", "bot.py"]
