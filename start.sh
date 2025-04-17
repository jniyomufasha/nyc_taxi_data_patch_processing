#!/bin/bash

# Start server and monitor profiles
echo "Starting server and monitor profiles..."
docker compose --profile server --profile monitor up -d

# Start flows profile
echo "Starting flows profile..."
docker compose --profile flows up -d

# Start frontend profile
echo "Starting frontend profile..."
docker compose --profile frontend up -d

echo "All profiles started!"
