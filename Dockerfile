# Use official Python image
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt


# Copy project files
COPY . .

# Ensure staticfiles directory exists and is writable
RUN mkdir -p /app/staticfiles && chmod -R 755 /app/staticfiles

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8080

# Start Gunicorn server
CMD ["gunicorn", "paycrypt_bank_gw.wsgi:application", "-b", "0.0.0.0:8080"]
