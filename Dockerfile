# Use an official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Create a non-root user and group for security purposes
# Running as a non-root user is a security best practice.
RUN addgroup --system app && adduser --system --group app

# Copy the requirements file and install dependencies
# This is done in a separate layer to leverage Docker's build cache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY . .

# Change the ownership of the application directory to the non-root user
RUN chown -R app:app /app

# Switch to the non-root user
USER app

# Command to run the application
CMD ["python", "main.py"]
