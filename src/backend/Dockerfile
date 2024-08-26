# Use the latest Ubuntu as the base image
FROM ubuntu:latest AS base

ENV PYTHONUNBUFFERED=1

COPY requirements.txt /var/www/html/requirements.txt

# Install system dependencies and Python dependencies in a single layer
RUN apt update && \
    apt install -y python3 python3-pip libpcap-dev libpq-dev && \
    mkdir -p /var/www/html && \
    python3 -m pip install --break-system-packages -r /var/www/html/requirements.txt

# Set the working directory and copy the application code
WORKDIR /var/www/html
COPY . /var/www/html/

# Expose the port the app runs on
EXPOSE 8000

# Set permissions and create necessary directories
RUN chmod +x /var/www/html/start.sh && \
    mkdir -p /var/www/html/static && \
    chmod -R 755 /var/www/html/static

# Define the command to run the application
CMD ["bash", "/var/www/html/start.sh"]
