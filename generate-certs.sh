#!/usr/bin/env bash
# Generates a self-signed TLS certificate for local/dev use.
# For production, replace these files with real certs from Let's Encrypt or your CA.
set -e

DOMAIN=${1:-localhost}
OUT=nginx/certs

mkdir -p "$OUT"

openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout "$OUT/key.pem" \
  -out "$OUT/cert.pem" \
  -subj "/CN=${DOMAIN}" \
  -addext "subjectAltName=DNS:${DOMAIN},DNS:localhost,IP:127.0.0.1"

echo ""
echo "Self-signed cert written to $OUT/"
echo "For production, replace with a real cert from Let's Encrypt:"
echo "  certbot certonly --standalone -d ${DOMAIN}"
echo "  cp /etc/letsencrypt/live/${DOMAIN}/fullchain.pem nginx/certs/cert.pem"
echo "  cp /etc/letsencrypt/live/${DOMAIN}/privkey.pem  nginx/certs/key.pem"
