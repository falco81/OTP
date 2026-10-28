#!/bin/bash
# sign.sh DIR - MANIFEST (the SHA-256 of every file) and its Ed25519 signature,
# so the pages may put the package in (1.0.37). The private key never leaves
# /home/claude/build/keys.
set -euo pipefail
d="${1:?folder}"
key=/home/claude/build/keys/otp-release-1.key
rm -f "$d/MANIFEST" "$d/MANIFEST.sig"
find "$d" -name __pycache__ -prune -exec rm -rf {} +
(cd "$d" && find . -type f ! -name MANIFEST ! -name MANIFEST.sig -printf '%P\n' | LC_ALL=C sort |
   while IFS= read -r f; do printf '%s  %s\n' "$(sha256sum "$f" | cut -d' ' -f1)" "$f"; done) > "$d/MANIFEST"
openssl pkeyutl -sign -inkey "$key" -rawin -in "$d/MANIFEST" -out "$d/MANIFEST.sig"
openssl pkeyutl -verify -pubin -inkey "$d/deploy/release-keys/otp-release-1.pub" -rawin \
    -in "$d/MANIFEST" -sigfile "$d/MANIFEST.sig" >/dev/null
echo "signed: $(wc -l < "$d/MANIFEST") files"
