#!/bin/bash
set -e

echo "==> Cloning repo..."
cd /home/ubuntu
if [ ! -d "SecureNet-SOC" ]; then
    git clone https://github.com/AbdelrahmanHaroun2004/SecureNet-SOC.git
fi

echo "==> Setting up .env..."
cd /home/ubuntu/SecureNet-SOC
cp .env.example .env

JWT=$(openssl rand -hex 32)
APIKEY=$(openssl rand -hex 32)
PGPASS=$(openssl rand -hex 16)

sed -i "s|JWT_SECRET=.*|JWT_SECRET=$JWT|" .env
sed -i "s|INTERNAL_API_KEY=.*|INTERNAL_API_KEY=$APIKEY|" .env
sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$PGPASS|" .env

echo "==> Starting Docker Compose..."
sudo docker compose up -d

echo "==> Waiting 30s for services to start..."
sleep 30

echo "==> Container status:"
sudo docker compose ps

echo "=========================================="
echo "  ALL DONE!"
echo "=========================================="
