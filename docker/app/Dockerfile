FROM python:3.12

ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app/src

# Установка uv
RUN pip install uv

# Создание пользователя с правами доступа
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/src && \
    chown -R appuser:appuser /app

# Рабочая директория
WORKDIR $APP_HOME

# Копирование файла зависимостей
COPY requirements.txt /tmp/requirements.txt

# Установка зависимостей через uv
RUN uv pip install --system -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Копирование .bashrc для настройки shell
COPY bashrc /home/appuser/.bashrc
RUN chown appuser:appuser /home/appuser/.bashrc && \
    chmod 644 /home/appuser/.bashrc

# Переключение на пользователя
USER appuser

SHELL ["/bin/bash", "-c"]

