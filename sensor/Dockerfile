FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for scapy
RUN apt-get update && apt-get install -y --no-install-recommends \
    tcpdump \
    libpcap0.8 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
