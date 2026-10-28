#!/bin/bash
# bump.sh NEW - one version everywhere: otp.py, the pages, the language files,
# the docs, the folder and the archive. Every change ships as a new version.
set -euo pipefail
cd "$(dirname "$0")"
new=${1:?new version}
old=$(sed -n "s/^__version__ = '\(.*\)'/\1/p" parts/00_head.py)
[ "$old" != "$new" ] || { echo "already $new"; exit 1; }
[ -d "out/otp-$new" ] && { echo "out/otp-$new exists"; exit 1; }
sed -i "s/^__version__ = '$old'/__version__ = '$new'/" parts/00_head.py
mv "out/otp-$old" "out/otp-$new"
d="out/otp-$new"
sed -i "s/const OTP_VERSION = '$old'/const OTP_VERSION = '$new'/" "$d/web/otp-page.php"
sed -i "s/\"version\": \"$old\"/\"version\": \"$new\"/" "$d/web/lang/"*.json "$d/docs/languages.md"
sed -i "s/otp-$old/otp-$new/g" "$d/INSTALL.md" "$d/README.md"
sed -i "s#out/otp-$old#out/otp-$new#g" build.sh
sed -i "s/\"version\":\"$old\"/\"version\":\"$new\"/" /home/claude/i18n/make_cs.py 2>/dev/null || true
sed -i "s/'version':'$old'/'version':'$new'/" /home/claude/i18n/make_cs.py 2>/dev/null || true
sed -i "s#out/otp-$old/#out/otp-$new/#" /home/claude/i18n/make_cs.py 2>/dev/null || true
bash build.sh
rm -rf "$d/__pycache__" "$d/test/__pycache__"
grep -rn --exclude=*.tar.gz "$old" "$d" | grep -v CHANGELOG.md | grep -vE "otp.py:.*(10000|310000)" || true
bash sign.sh "$d"
(cd out && tar --owner=0 --group=0 -czf "otp-$new.tar.gz" "otp-$new")
echo "otp $old -> $new: out/otp-$new.tar.gz"
