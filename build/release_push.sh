#!/bin/bash
# Put out/otp-VERSION.tar.gz into falco81/OTP release/, keep only the newest 10 there.
set -e
V="$1"; R=/home/claude/otp
cd "$R"
git fetch -q --depth 1 origin main && git reset -q --hard origin/main
cp "/home/claude/build/out/otp-$V.tar.gz" release/
git add "release/otp-$V.tar.gz"
ls release/otp-*.tar.gz | sed 's|release/otp-||; s|\.tar\.gz$||' | sort -V | head -n -10 | while read old; do git rm -q "release/otp-$old.tar.gz"; echo "removed $old"; done
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -q -m "release: otp $V

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018bm7haoJxKbiLKmngYgoQA"
git push -q origin main
git ls-tree --name-only HEAD release/
