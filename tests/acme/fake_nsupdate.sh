#!/bin/bash
# nsupdate for the tests: reads the update from stdin, checks the TSIG key
# file it was given (-k FILE, never the secret itself on the command line),
# and writes the TXT record into the test CA's DNS ($DNSJSON).
key=""
while [[ $# -gt 0 ]]; do case "$1" in -k) key="$2"; shift 2;; *) echo "unexpected $1" >&2; exit 2;; esac; done
[[ -f "$key" ]] || { echo "no key file" >&2; exit 3; }
grep -q 'secret "c2VjcmV0LWtleS1mb3ItdGVzdHM="' "$key" || { echo "wrong key" >&2; exit 4; }
[[ "$(stat -c %a "$key")" == 600 ]] || { echo "key file not 0600" >&2; exit 5; }
echo "$(stat -c %a "$key") $(cat "$key" | head -1)" >> "$DNSJSON.keys"
export NSU_SCRIPT="$(cat)"
python3 - "$DNSJSON" <<'PY'
import sys, json, re, os
f = sys.argv[1]
try: d = json.load(open(f))
except Exception: d = {}
for ln in os.environ['NSU_SCRIPT'].splitlines():
    m = re.match(r'update (add|delete) (\S+) (?:\d+ )?TXT "(.*)"', ln)
    if m:
        op, rr, v = m.groups()
        vals = d.setdefault(rr, [])
        if op == 'add' and v not in vals: vals.append(v)
        if op == 'delete' and v in vals: vals.remove(v)
json.dump(d, open(f, 'w'))
PY
