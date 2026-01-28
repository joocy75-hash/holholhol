#!/bin/bash
set -e

echo "=== PokerKit Holdem Deploy ==="
echo "Started at: $(date)"

cd /app/holdem

echo ""
echo "[1/6] Pulling latest code..."
git pull origin main

echo ""
echo "[2/6] Updating Backend..."
cd /app/holdem/backend
source venv/bin/activate
pip install -r requirements.txt -q
deactivate

echo ""
echo "[3/6] Updating Admin Backend..."
cd /app/holdem/admin-backend
source venv/bin/activate
pip install -r requirements.txt -q
deactivate

echo ""
echo "[4/6] Building Frontend..."
cd /app/holdem/frontend
pnpm install --frozen-lockfile
pnpm run build
cp -r public .next/standalone/public
cp -r .next/static .next/standalone/.next/static

echo ""
echo "[5/6] Building Admin Frontend..."
cd /app/holdem/admin-frontend
pnpm install --frozen-lockfile
pnpm run build
cp -r public .next/standalone/public 2>/dev/null || true
cp -r .next/static .next/standalone/.next/static

echo ""
echo "[6/6] Restarting PM2..."
cd /app/holdem
pm2 reload ecosystem.config.cjs

echo ""
pm2 status

echo ""
echo "=== Deploy Complete ==="
echo "Finished at: $(date)"
