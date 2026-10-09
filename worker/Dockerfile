FROM python:3.12-slim
WORKDIR /app
COPY main.py /app/main.py
RUN useradd --create-home --uid 10001 worker
USER worker
CMD ["python", "-u", "/app/main.py"]
