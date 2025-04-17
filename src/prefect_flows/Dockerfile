FROM bitnami/spark:3.5.5

# Set working directory
WORKDIR /app

COPY requirements.txt /app/
RUN pip install -r requirements.txt

# Switch to root to create a new user and group
USER root

RUN apt-get update && \
apt-get install -y curl

# Create a non-root user and group
RUN groupadd -r sparkuser && useradd -r -g sparkuser sparkuser

# Create the directory and set ownership to the new user
RUN mkdir -p /opt/spark/jars && \
    chown -R sparkuser:sparkuser /opt/spark/jars

# Switch back to non-root user
# USER sparkuser

# Download PostgreSQL JDBC driver
RUN curl -o /opt/spark/jars/postgresql-42.5.0.jar https://jdbc.postgresql.org/download/postgresql-42.5.0.jar

# Copy application files
COPY main.py /app/

# Run the script
CMD ["python", "main.py"]
