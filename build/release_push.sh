#!/bin/bash
# Put out/otp-VERSION.tar.gz into falco81/OTP release/ (the newest 10 kept there),
# and the package unpacked at the root of main - the repository shows the
# release it holds (1.0.146).
set -e
V="$1"; R=/home/claude/otp
PKG="/home/claude/build/out/otp-$V.tar.gz"
[[ -f "$PKG" ]] || { echo "no $PKG"; exit 1; }
cd "$R"
git fetch -q --depth 1 origin main && git reset -q --hard origin/main
# The root as the package has it: what the previous package had and this one
# no longer has goes - only that (1.0.147): a file put there by hand
# (LICENSE.md) is not the package's and stays.
NEWLIST="$(mktemp)"
tar tzf "$PKG" | sed -n 's|^otp-[^/]*/||p' | grep -v '/$' | sort > "$NEWLIST"
if [[ -f MANIFEST ]]; then
    { awk '{print $2}' MANIFEST; echo MANIFEST; echo MANIFEST.sig; } | sort -u | comm -23 - "$NEWLIST" |
        while read -r gone; do [[ -n "$gone" && -e "$gone" ]] && git rm -q -- "$gone" && echo "gone: $gone"; done
fi
rm -f "$NEWLIST"
tar xzf "$PKG" --strip-components=1 -C "$R" --exclude='*/__pycache__' --exclude='*.pyc'
cp "$PKG" release/
git add -A .
ls release/otp-*.tar.gz | sed 's|release/otp-||; s|\.tar\.gz$||' | sort -V | head -n -10 | while read old; do git rm -q "release/otp-$old.tar.gz"; echo "removed $old"; done
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -q -m "release: otp $V

The package unpacked at the root, and release/otp-$V.tar.gz.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XtSgvua4j9gpLUBeqw2NjB"
git push -q origin main
grep -m1 '^__version__' otp.py
git ls-tree --name-only HEAD release/ | tail -3
