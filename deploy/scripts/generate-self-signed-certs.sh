#!/bin/bash
# Generate self-signed SSL certificates for development/testing

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the project root directory (parent of scripts/)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
# Set certificate directory
CERT_DIR="$PROJECT_ROOT/data/certs/nginx"

echo "Project root: $PROJECT_ROOT"
echo "Certificate directory: $CERT_DIR"
echo ""

mkdir -p "$CERT_DIR"

echo "Generating SSL certificates..."

# Generate certificate for aimychats.com
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$CERT_DIR/aimychats.com.key" \
  -out "$CERT_DIR/aimychats.com.crt" \
  -subj "/C=CN/ST=Beijing/L=Beijing/O=AImyChats/CN=aimychats.com" \
  -addext "subjectAltName=DNS:aimychats.com,DNS:www.aimychats.com"

# Generate certificate for app.aimychats.com
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$CERT_DIR/app.aimychats.com.key" \
  -out "$CERT_DIR/app.aimychats.com.crt" \
  -subj "/C=CN/ST=Beijing/L=Beijing/O=AImyChats/CN=app.aimychats.com"

echo "✓ Certificates generated in $CERT_DIR"
ls -lh "$CERT_DIR"
