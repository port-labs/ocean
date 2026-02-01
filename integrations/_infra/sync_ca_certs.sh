#!/bin/bash

# Script to sync CA certificates from privileged locations to unprivileged user directory
# This handles cases where CA certificates are mounted or updated at runtime

CERT_SOURCE_DIRS="/etc/ssl/certs /usr/share/ca-certificates /usr/local/share/ca-certificates"
USER_CERT_DIR="/home/ocean/.local/share/ca-certificates"

# Create user certificate directory if it doesn't exist
mkdir -p "$USER_CERT_DIR"

# Sync certificates from all possible source directories
for source_dir in $CERT_SOURCE_DIRS; do
    if [ -d "$source_dir" ] && [ -r "$source_dir" ]; then
        # Copy certificates, ignore errors for files we can't read
        find "$source_dir" -type f \( -name "*.crt" -o -name "*.pem" -o -name "*.cer" \) 2>/dev/null | while read cert_file; do
            if [ -r "$cert_file" ]; then
                cp "$cert_file" "$USER_CERT_DIR/" 2>/dev/null || true
            fi
        done
    fi
done

# Set proper permissions - files to 644, directory to 755
chmod 755 "$USER_CERT_DIR" 2>/dev/null || true
chmod 644 "$USER_CERT_DIR"/* 2>/dev/null || true

# Create a consolidated CA bundle file
cat "$USER_CERT_DIR"/*.crt "$USER_CERT_DIR"/*.pem 2>/dev/null > "$USER_CERT_DIR/ca-certificates.crt" || true

# Export environment variables for SSL
export SSL_CERT_DIR="$USER_CERT_DIR"
export SSL_CERT_FILE="$USER_CERT_DIR/ca-certificates.crt"
export CURL_CA_BUNDLE="$USER_CERT_DIR/ca-certificates.crt"
export REQUESTS_CA_BUNDLE="$USER_CERT_DIR/ca-certificates.crt"

echo "CA certificates synced to $USER_CERT_DIR"
