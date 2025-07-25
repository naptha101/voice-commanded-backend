# Use Python base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy all files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy models
RUN chmod +x setup.sh && ./setup.sh

# Expose port for Hugging Face
EXPOSE 7860

# Run app with gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:7860", "app:app"]
