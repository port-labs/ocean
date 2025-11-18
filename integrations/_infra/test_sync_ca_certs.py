#!/usr/bin/env python3
"""
Test suite for sync_ca_certs.sh script functionality.

This module tests the CA certificate synchronization script that copies
certificates from system locations to unprivileged user directories.
"""

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime
import pytest


class TestCACertSync:
    """Test cases for CA certificate synchronization functionality."""

    def setup_method(self):
        """Set up test environment before each test."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.source_dirs = [
            self.test_dir / "etc_ssl_certs",
            self.test_dir / "usr_share_ca_certs",
            self.test_dir / "usr_local_share_ca_certs"
        ]
        self.user_cert_dir = self.test_dir / "home_ocean" / ".local" / "share" / "ca-certificates"

        # Create source directories
        for source_dir in self.source_dirs:
            source_dir.mkdir(parents=True, exist_ok=True)

        # Create user cert directory
        self.user_cert_dir.mkdir(parents=True, exist_ok=True)

    def teardown_method(self):
        """Clean up test environment after each test."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def create_test_certificate(self, filename: str, common_name: str = "Test CA") -> Path:
        """Create a self-signed test certificate."""
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Test"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TestOrg"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=365)
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        ).sign(private_key, hashes.SHA256())

        # Write certificate to file
        cert_path = self.source_dirs[0] / filename
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        return cert_path

    def create_sync_script(self) -> Path:
        """Create a modified sync script for testing."""
        script_content = f"""#!/bin/bash

# Modified sync script for testing
CERT_SOURCE_DIRS="{' '.join(str(d) for d in self.source_dirs)}"
USER_CERT_DIR="{self.user_cert_dir}"

# Create user certificate directory if it doesn't exist
mkdir -p "$USER_CERT_DIR"

# Sync certificates from all possible source directories
for source_dir in $CERT_SOURCE_DIRS; do
    if [ -d "$source_dir" ] && [ -r "$source_dir" ]; then
        # Copy certificates, ignore errors for files we can't read
        find "$source_dir" -type f \\( -name "*.crt" -o -name "*.pem" -o -name "*.cer" \\) 2>/dev/null | while read cert_file; do
            if [ -r "$cert_file" ]; then
                cp "$cert_file" "$USER_CERT_DIR/" 2>/dev/null || true
            fi
        done
    fi
done

# Set proper permissions
chmod -R 644 "$USER_CERT_DIR"/* 2>/dev/null || true

# Create a consolidated CA bundle file
cat "$USER_CERT_DIR"/*.crt "$USER_CERT_DIR"/*.pem 2>/dev/null > "$USER_CERT_DIR/ca-certificates.crt" || true

# Export environment variables for SSL
export SSL_CERT_DIR="$USER_CERT_DIR"
export SSL_CERT_FILE="$USER_CERT_DIR/ca-certificates.crt"
export CURL_CA_BUNDLE="$USER_CERT_DIR/ca-certificates.crt"
export REQUESTS_CA_BUNDLE="$USER_CERT_DIR/ca-certificates.crt"

echo "CA certificates synced to $USER_CERT_DIR"
"""
        script_path = self.test_dir / "test_sync_ca_certs.sh"
        with open(script_path, "w") as f:
            f.write(script_content)
        script_path.chmod(0o755)
        return script_path

    def test_script_copies_certificates(self):
        """Test that the script copies certificates from source directories."""
        # Create test certificates
        cert1 = self.create_test_certificate("test1.crt", "Test CA 1")
        cert2 = self.create_test_certificate("test2.crt", "Test CA 2")

        # Create additional certificate in second source directory
        cert3_path = self.source_dirs[1] / "test3.pem"
        shutil.copy2(cert1, cert3_path)

        # Run sync script
        script = self.create_sync_script()
        result = subprocess.run([str(script)], capture_output=True, text=True)

        assert result.returncode == 0
        assert "CA certificates synced" in result.stdout

        # Verify certificates were copied
        copied_certs = list(self.user_cert_dir.glob("*.crt")) + list(self.user_cert_dir.glob("*.pem"))
        assert len(copied_certs) >= 2

        # Check that certificate contents are preserved
        for cert_file in copied_certs:
            if cert_file.name != "ca-certificates.crt":
                assert cert_file.stat().st_size > 0
                with open(cert_file, "r") as f:
                    content = f.read()
                    assert "-----BEGIN CERTIFICATE-----" in content
                    assert "-----END CERTIFICATE-----" in content

    def test_script_creates_ca_bundle(self):
        """Test that the script creates a consolidated CA bundle."""
        # Create test certificates
        self.create_test_certificate("test1.crt", "Test CA 1")
        self.create_test_certificate("test2.crt", "Test CA 2")

        # Run sync script
        script = self.create_sync_script()
        result = subprocess.run([str(script)], capture_output=True, text=True)

        assert result.returncode == 0

        # Verify CA bundle was created
        ca_bundle = self.user_cert_dir / "ca-certificates.crt"
        assert ca_bundle.exists()
        assert ca_bundle.stat().st_size > 0

        # Verify bundle contains multiple certificates
        with open(ca_bundle, "r") as f:
            content = f.read()
            cert_count = content.count("-----BEGIN CERTIFICATE-----")
            assert cert_count >= 2

    def test_script_handles_empty_directories(self):
        """Test that the script handles empty source directories gracefully."""
        # Run sync script with empty directories
        script = self.create_sync_script()
        result = subprocess.run([str(script)], capture_output=True, text=True)

        assert result.returncode == 0
        assert "CA certificates synced" in result.stdout

        # User cert directory should exist but be mostly empty
        assert self.user_cert_dir.exists()

    def test_script_handles_missing_directories(self):
        """Test that the script handles missing source directories gracefully."""
        # Remove one of the source directories
        shutil.rmtree(self.source_dirs[0])

        # Create certificate in remaining directory
        self.create_test_certificate("test.crt", "Test CA")

        # Run sync script
        script = self.create_sync_script()
        result = subprocess.run([str(script)], capture_output=True, text=True)

        assert result.returncode == 0
        assert "CA certificates synced" in result.stdout

    def test_certificate_permissions(self):
        """Test that copied certificates have correct permissions."""
        # Create test certificate
        self.create_test_certificate("test.crt", "Test CA")

        # Run sync script
        script = self.create_sync_script()
        result = subprocess.run([str(script)], capture_output=True, text=True)

        assert result.returncode == 0

        # Check permissions on copied certificates
        for cert_file in self.user_cert_dir.glob("*"):
            if cert_file.is_file():
                # Check that files are readable by owner and group
                stat_info = cert_file.stat()
                mode = stat_info.st_mode
                assert mode & 0o644 == 0o644  # At least 644 permissions

    def test_certificate_validation(self):
        """Test that copied certificates are valid X.509 certificates."""
        # Create test certificate
        self.create_test_certificate("test.crt", "Test CA")

        # Run sync script
        script = self.create_sync_script()
        result = subprocess.run([str(script)], capture_output=True, text=True)

        assert result.returncode == 0

        # Validate certificate using OpenSSL
        ca_bundle = self.user_cert_dir / "ca-certificates.crt"
        if ca_bundle.exists():
            result = subprocess.run([
                "openssl", "x509", "-in", str(ca_bundle),
                "-text", "-noout"
            ], capture_output=True, text=True)

            assert result.returncode == 0
            assert "Test CA" in result.stdout
            assert "Certificate:" in result.stdout

    def test_script_is_idempotent(self):
        """Test that running the script multiple times produces the same result."""
        # Create test certificate
        self.create_test_certificate("test.crt", "Test CA")

        # Run sync script twice
        script = self.create_sync_script()

        result1 = subprocess.run([str(script)], capture_output=True, text=True)
        assert result1.returncode == 0

        # Get initial state
        initial_files = list(self.user_cert_dir.glob("*"))
        initial_bundle_size = (self.user_cert_dir / "ca-certificates.crt").stat().st_size

        result2 = subprocess.run([str(script)], capture_output=True, text=True)
        assert result2.returncode == 0

        # Verify state is the same
        final_files = list(self.user_cert_dir.glob("*"))
        final_bundle_size = (self.user_cert_dir / "ca-certificates.crt").stat().st_size

        assert len(initial_files) == len(final_files)
        assert initial_bundle_size == final_bundle_size

    def test_different_certificate_formats(self):
        """Test that the script handles different certificate file extensions."""
        # Create certificates with different extensions
        cert_crt = self.create_test_certificate("test1.crt", "Test CA CRT")

        # Copy to create .pem and .cer versions
        cert_pem = self.source_dirs[1] / "test2.pem"
        cert_cer = self.source_dirs[2] / "test3.cer"
        shutil.copy2(cert_crt, cert_pem)
        shutil.copy2(cert_crt, cert_cer)

        # Run sync script
        script = self.create_sync_script()
        result = subprocess.run([str(script)], capture_output=True, text=True)

        assert result.returncode == 0

        # Verify all certificate formats were copied
        copied_files = list(self.user_cert_dir.glob("*"))
        extensions = {f.suffix for f in copied_files}
        assert ".crt" in extensions
        assert ".pem" in extensions
        assert ".cer" in extensions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
