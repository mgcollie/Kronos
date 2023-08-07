# Use an official Python runtime as the base image
FROM python:3.9-slim

# Set the working directory in the Docker image
WORKDIR /app

# Create a non-root user
RUN useradd -m kronos

# Switch to the new user
USER kronos

# Copy the local application files to the container
COPY --chown=kronos ./main.py /app/main.py
COPY --chown=kronos ./requirements.txt /app/requirements.txt

# Install the required Python packages (as root)
USER root
RUN pip install --no-cache-dir -r requirements.txt

# Switch back to the app user
USER kronos

# This environment variable ensures that the python output is set straight
# to the terminal without buffering it first
ENV PYTHONUNBUFFERED 1

# Command to run the application
CMD ["python", "./main.py"]
