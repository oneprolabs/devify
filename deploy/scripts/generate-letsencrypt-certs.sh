#!/bin/bash
# Generate Let's Encrypt SSL certificates for production

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the project root directory (parent of scripts/)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
# Set certificate directory
CERT_DIR="$PROJECT_ROOT/data/certs/nginx"
EMAIL="your-email@example.com"  # Change this to your email

echo "Project root: $PROJECT_ROOT"
echo "Certificate directory: $CERT_DIR"
echo ""

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    echo "certbot not found. Installing..."
    sudo apt-get update
    sudo apt-get install -y certbot
fi

echo "Generating Let's Encrypt certificates..."
echo "Note: Your domain must be publicly accessible on port 80"

# Generate certificate for aimychats.com and www.aimychats.com
sudo certbot certonly --standalone \
  --non-interactive \
  --agree-tos \
  --email "$EMAIL" \
  -d aimychats.com \
  -d www.aimychats.com

# Generate certificate for app.aimychats.com
sudo certbot certonly --standalone \
  --non-interactive \
  --agree-tos \
  --email "$EMAIL" \
  -d app.aimychats.com

# Copy certificates to nginx cert directory
mkdir -p "$CERT_DIR"
sudo cp /etc/letsencrypt/live/aimychats.com/fullchain.pem "$CERT_DIR/aimychats.com.crt"
sudo cp /etc/letsencrypt/live/aimychats.com/privkey.pem "$CERT_DIR/aimychats.com.key"
sudo cp /etc/letsencrypt/live/app.aimychats.com/fullchain.pem "$CERT_DIR/app.aimychats.com.crt"
sudo cp /etc/letsencrypt/live/app.aimychats.com/privkey.pem "$CERT_DIR/app.aimychats.com.key"

# Set proper permissions
sudo chown -R $USER:$USER "$CERT_DIR"
sudo chmod 600 "$CERT_DIR"/*.key
sudo chmod 644 "$CERT_DIR"/*.crt

echo "✓ Let's Encrypt certificates generated and copied to $CERT_DIR"
ls -lh "$CERT_DIR"

echo ""
echo "Note: Certificates will expire in 90 days. Set up auto-renewal:"
echo "sudo certbot renew --dry-run"
