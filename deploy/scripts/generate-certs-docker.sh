#!/bin/bash
# Generate Let's Encrypt SSL certificates using Docker certbot

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the project root directory (parent of scripts/)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
# Set certificate directory
CERT_DIR="$PROJECT_ROOT/data/certs/nginx"
EMAIL="your-email@example.com"  # Change this to your email
DOMAINS="aimychats.com,www.aimychats.com,app.aimychats.com"

echo "Project root: $PROJECT_ROOT"
echo "Certificate directory: $CERT_DIR"
echo ""

mkdir -p "$CERT_DIR"
mkdir -p "$PROJECT_ROOT/data/certbot/www"
mkdir -p "$PROJECT_ROOT/data/certbot/conf"

echo "Generating Let's Encrypt certificates using Docker..."
echo "Domains: $DOMAINS"

# Run certbot in Docker container
docker run -it --rm \
  -v "$PROJECT_ROOT/data/certbot/conf:/etc/letsencrypt" \
  -v "$PROJECT_ROOT/data/certbot/www:/var/www/certbot" \
  -p 80:80 \
  certbot/certbot certonly \
  --standalone \
  --non-interactive \
  --agree-tos \
  --email "$EMAIL" \
  --preferred-challenges http \
  -d aimychats.com \
  -d www.aimychats.com \
  -d app.aimychats.com

# Copy certificates to nginx cert directory
if [ -d "$PROJECT_ROOT/data/certbot/conf/live/aimychats.com" ]; then
  cp "$PROJECT_ROOT/data/certbot/conf/live/aimychats.com/fullchain.pem" "$CERT_DIR/aimychats.com.crt"
  cp "$PROJECT_ROOT/data/certbot/conf/live/aimychats.com/privkey.pem" "$CERT_DIR/aimychats.com.key"
  cp "$PROJECT_ROOT/data/certbot/conf/live/aimychats.com/fullchain.pem" "$CERT_DIR/app.aimychats.com.crt"
  cp "$PROJECT_ROOT/data/certbot/conf/live/aimychats.com/privkey.pem" "$CERT_DIR/app.aimychats.com.key"

  chmod 600 "$CERT_DIR"/*.key
  chmod 644 "$CERT_DIR"/*.crt

  echo "✓ Certificates generated and copied to $CERT_DIR"
  ls -lh "$CERT_DIR"
else
  echo "✗ Certificate generation failed"
  exit 1
fi
