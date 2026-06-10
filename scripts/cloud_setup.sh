#!/bin/bash
# ================================================================
# SecureNet SOC — Cloud Server Setup Script
# ================================================================
# Run this on a fresh Ubuntu 22.04/24.04 VPS
#
# Usage:
#   1. SSH into your VPS:  ssh root@<your-server-ip>
#   2. Upload this script: scp scripts/cloud_setup.sh root@<ip>:~/
#   3. Run it:             chmod +x cloud_setup.sh && ./cloud_setup.sh
# ================================================================

set -e

echo "============================================"
echo "  SecureNet SOC — Cloud Server Setup"
echo "============================================"

# -----------------------------------------------
# Step 1: System Update + Docker Installation
# -----------------------------------------------
echo "[1/6] Installing Docker..."
apt-get update -y
apt-get install -y ca-certificates curl gnupg git

# Docker official repo
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

systemctl enable docker
systemctl start docker

echo "✅ Docker installed: $(docker --version)"

# -----------------------------------------------
# Step 2: Create non-root user
# -----------------------------------------------
echo "[2/6] Creating securenet user..."
if ! id "securenet" &>/dev/null; then
    useradd -m -s /bin/bash -G docker securenet
    echo "securenet ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/securenet
    echo "✅ User 'securenet' created"
else
    echo "⏭️  User 'securenet' already exists"
fi

# -----------------------------------------------
# Step 3: Firewall Setup
# -----------------------------------------------
echo "[3/6] Configuring firewall..."
apt-get install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp      # HTTP (Traefik)
ufw allow 443/tcp     # HTTPS (Traefik)
ufw allow 8005/tcp    # Mobile Gateway (direct, for development)
ufw allow 8000/tcp    # API Gateway (direct, for development)
ufw --force enable
echo "✅ Firewall configured"

# -----------------------------------------------
# Step 4: Setup swap (for small VPS)
# -----------------------------------------------
echo "[4/6] Setting up swap space..."
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "✅ 2GB swap created"
else
    echo "⏭️  Swap already exists"
fi

# -----------------------------------------------
# Step 5: Clone repository
# -----------------------------------------------
echo "[5/6] Cloning SecureNet repository..."
PROJ_DIR="/home/securenet/SecureNet_IDS_Project"
if [ ! -d "$PROJ_DIR" ]; then
    sudo -u securenet git clone https://github.com/YOUR_USERNAME/SecureNet-SOC.git "$PROJ_DIR"
    echo "✅ Repository cloned"
else
    echo "⏭️  Repository already exists, pulling latest..."
    cd "$PROJ_DIR" && sudo -u securenet git pull
fi

# -----------------------------------------------
# Step 6: Generate .env
# -----------------------------------------------
echo "[6/6] Generating environment file..."
cd "$PROJ_DIR"

if [ ! -f .env ]; then
    cp .env.example .env

    # Generate cryptographic secrets
    JWT_SECRET=$(openssl rand -hex 32)
    INTERNAL_API_KEY=$(openssl rand -hex 32)
    POSTGRES_PASSWORD=$(openssl rand -hex 16)

    sed -i "s|JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" .env
    sed -i "s|INTERNAL_API_KEY=.*|INTERNAL_API_KEY=$INTERNAL_API_KEY|" .env
    sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$POSTGRES_PASSWORD|" .env

    chown securenet:securenet .env
    chmod 600 .env
    echo "✅ .env generated with real secrets"
else
    echo "⏭️  .env already exists"
fi

echo ""
echo "============================================"
echo "  ✅ Server setup complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Edit .env to add your OPENROUTER_API_KEY:"
echo "     nano $PROJ_DIR/.env"
echo ""
echo "  2. Copy your trained ML model to the server:"
echo "     scp ml_engine/models/model.joblib securenet@<ip>:$PROJ_DIR/ml_engine/models/"
echo "     scp ml_engine/models/model_metadata.json securenet@<ip>:$PROJ_DIR/ml_engine/models/"
echo ""
echo "  3. Start the services:"
echo "     cd $PROJ_DIR"
echo "     docker compose up -d"
echo ""
echo "  4. Run database migrations:"
echo "     docker compose exec gateway python -c 'from shared.database import *; import asyncio; asyncio.run(init_db())'"
echo ""
echo "  5. Create admin user:"
echo "     docker compose exec gateway python manage.py create-admin --email admin@securenet.local"
echo ""
echo "  Mobile Gateway will be at: http://$(curl -s ifconfig.me):8005"
echo "  Swagger Docs:              http://$(curl -s ifconfig.me):8005/docs"
echo ""
