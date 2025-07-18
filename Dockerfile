# Use an official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Create a non-root user and group for security purposes
# Running as a non-root user is a security best practice.
RUN addgroup --system app && adduser --system --group app

# Copy the requirements file first for build cache optimization
COPY requirements.txt .

# Install system dependencies needed for building Python packages (like tgcrypto),
# then install the packages, and finally remove the build dependencies to keep the image small.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the rest of the application's code into the container
COPY . .

# Change the ownership of the application directory to the non-root user
RUN chown -R app:app /app

# Switch to the non-root user
USER app

# Command to run the application
CMD ["python", "main.py"]
