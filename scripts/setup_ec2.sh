#!/usr/bin/env bash
# Setup script para deploy na AWS EC2 (Ubuntu 24.04 LTS)
# Uso: bash setup_ec2.sh
set -euo pipefail

REPO_URL="https://github.com/gutoportelaa/estudo-chatbot.git"
APP_DIR="$HOME/estudo-chatbot"

# --- Dependências ---
echo "==> Instalando Docker e Git..."
sudo apt-get update -qq
sudo apt-get install -y -qq docker.io docker-compose-plugin git

sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

# --- Repositório ---
if [ -d "$APP_DIR" ]; then
  echo "==> Repositório já existe, atualizando..."
  git -C "$APP_DIR" pull
else
  echo "==> Clonando repositório..."
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"

# --- Variáveis de ambiente ---
if [ ! -f .env ]; then
  echo "==> Criando .env..."

  PUBLIC_IP=$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4 || echo "")
  if [ -z "$PUBLIC_IP" ]; then
    read -rp "IP público da EC2 não detectado. Informe manualmente: " PUBLIC_IP
  fi

  cat > .env <<EOF
DB_PASSWORD=$(openssl rand -hex 16)
GEMINI_API_KEY=${GEMINI_API_KEY:-your_gemini_api_key_here}
SECRET_KEY=$(openssl rand -hex 32)
VITE_API_URL=http://${PUBLIC_IP}:8000
EOF

  echo "==> .env criado. Edite GEMINI_API_KEY antes de continuar se necessário."
  echo "    nano .env"
else
  echo "==> .env já existe, mantendo configurações."
fi

# --- Containers ---
echo "==> Subindo containers..."
# newgrp não propaga em scripts; sg garante que docker funcione sem logout
sg docker -c "docker compose up -d --build"

# --- Verificação ---
echo "==> Aguardando API ficar disponível..."
for i in $(seq 1 12); do
  if curl -sf http://localhost:8000/health > /dev/null; then
    echo "==> Health check OK!"
    break
  fi
  echo "    tentativa $i/12..."
  sleep 5
done

PUBLIC_IP=$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4 || echo "<IP_PUBLICO>")
echo ""
echo "Deploy concluído!"
echo "  Web: http://${PUBLIC_IP}"
echo "  API: http://${PUBLIC_IP}:8000/health"
