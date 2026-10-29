FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --create-home app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY config.yaml .
COPY src ./src

USER app

EXPOSE 8080

CMD ["streamlit", "run", "src/web_app/app.py", "--server.address=0.0.0.0", "--server.port=8080", "--server.headless=true", "--browser.gatherUsageStats=false"]
