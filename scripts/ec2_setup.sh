#!/bin/bash
set -e

echo "=========================================="
echo "  Step 1: Installing Docker..."
echo "=========================================="
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl git

sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker ubuntu

echo "=========================================="
echo "  Step 2: Creating swap..."
echo "=========================================="
if [ ! -f /swapfile ]; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "Swap created"
else
    echo "Swap exists"
fi

echo "=========================================="
echo "  Step 3: Cloning SecureNet..."
echo "=========================================="
cd /home/ubuntu
if [ ! -d "SecureNet-SOC" ]; then
    git clone https://github.com/AbdelrahmanHaroun2004/SecureNet-SOC.git
else
    cd SecureNet-SOC && git pull && cd ..
fi

echo "=========================================="
echo "  Step 4: Setting up .env..."
echo "=========================================="
cd /home/ubuntu/SecureNet-SOC
if [ ! -f .env ]; then
    cp .env.example .env
    JWT=$(openssl rand -hex 32)
    APIKEY=$(openssl rand -hex 32)
    PGPASS=$(openssl rand -hex 16)
    sed -i "s|JWT_SECRET=.*|JWT_SECRET=$JWT|" .env
    sed -i "s|INTERNAL_API_KEY=.*|INTERNAL_API_KEY=$APIKEY|" .env
    sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$PGPASS|" .env
    echo ".env created with real secrets"
else
    echo ".env already exists"
fi

echo "=========================================="
echo "  ALL SETUP COMPLETE!"
echo "  Next: upload ML model, then docker compose up -d"
echo "=========================================="
