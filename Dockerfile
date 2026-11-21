FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for audio & networking
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir edge-tts python-dotenv pylibsrtp

# Copy application files
COPY . .

# Expose HTTP WebRTC (8080) and SIP UDP (5060)
EXPOSE 8080/tcp
EXPOSE 5060/udp

# Run TARS Server
CMD ["python", "-u", "call_server.py"]
