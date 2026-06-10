#!/bin/bash
set -e
cd /home/ubuntu/SecureNet-SOC

echo "==> Initializing database..."
cat << 'EOF' > db_init.py
import asyncio
from shared.database import engine, Base

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(init())
EOF

sudo docker compose cp db_init.py gateway:/app/db_init.py
sudo docker compose exec -T gateway python /app/db_init.py

echo "==> Creating admin user..."
sudo docker compose exec -T gateway python manage.py create-admin --email admin@securenet.local --password AdminPass123! || true

echo "==> Creating mobile dev user..."
sudo docker compose exec -T gateway python manage.py create-admin --email mobiledev@securenet.local --password MobileDev123! --role analyst || true

echo "==> Testing mobile gateway..."
curl -s http://localhost:8005/health

echo ""
echo "=========================================="
echo "  SETUP COMPLETE!"
echo "=========================================="
