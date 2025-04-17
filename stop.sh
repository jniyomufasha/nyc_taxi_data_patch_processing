#!/bin/bash

# Stop frontend profile
echo "Stopping frontend profile..."
docker compose --profile frontend down

# Stop flows profile
echo "Stopping flows profile..."
docker compose --profile flows down

# Stop server and monitor profiles
echo "Stopping server and monitor profiles..."
docker compose --profile server --profile monitor down

echo "All profiles stopped!"
