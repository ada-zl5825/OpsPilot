FROM python:3.12.8-slim-bookworm

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app/simulator

EXPOSE 8080
CMD ["uvicorn", "simulator.services.gateway.main:app", "--host", "0.0.0.0", "--port", "8080"]
