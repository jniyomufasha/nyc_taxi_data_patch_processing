FROM python:3.10.17-alpine3.21

# Set working directory
WORKDIR /app

COPY requirements.txt /app/
RUN pip install -r requirements.txt

# Copy application files
COPY main.py /app/
COPY utils.py /app/

# Run the script
CMD ["python", "main.py"]
