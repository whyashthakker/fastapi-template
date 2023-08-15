FROM python:3.10-slim-buster

ENV PYTHONUNBUFFERED 1

# Define the PORT environment variable, defaulting to 8000
ENV PORT=8000

WORKDIR /app

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Copy and set execution permissions for wait-for-it.sh
COPY wait-for-it.sh /app/
RUN chmod +x /app/wait-for-it.sh

# Copy requirements.txt and install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy the rest of the application
COPY . /app/

# Use the $PORT variable in the command
CMD uvicorn app:app --host 0.0.0.0 --port $PORT
