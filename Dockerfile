FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
# This is done first to leverage Docker's build cache.
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --trusted-host pypi.python.org -r requirements.txt

# Copy the rest of the application's code into the container at /app
COPY . .

# Command to run the application
CMD ["python", "main.py"]
