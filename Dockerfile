FROM python:3.9-slim


ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/homework

WORKDIR /app

COPY requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir requests

COPY . /app/

CMD ["pytest", "tests/"]
