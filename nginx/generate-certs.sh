#!/bin/bash
# Generates a self-signed TLS certificate for local development.
# For production, replace with a real certificate (Let's Encrypt, etc.)
mkdir -p certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/key.pem \
  -out certs/cert.pem \
  -subj "/C=US/ST=Dev/L=Dev/O=BabyFeeder/CN=localhost"
echo "Self-signed certificate generated in nginx/certs/"
