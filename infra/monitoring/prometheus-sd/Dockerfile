FROM python:3.11-slim

WORKDIR /app

# Install AWS CLI
RUN apt-get update && apt-get install -y awscli && rm -rf /var/lib/apt/lists/*

# Copy service discovery script
COPY update-targets.py /app/

# Run script every 30 seconds
CMD ["python", "-c", "import time, subprocess; [subprocess.run(['python', '/app/update-targets.py']) or time.sleep(30) for _ in iter(int, 1)]"]

