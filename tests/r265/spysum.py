import sys, collections, re
f = sys.argv[1]; depth = int(sys.argv[2]) if len(sys.argv) > 2 else 1
tot = 0; fn = collections.Counter(); own = collections.Counter(); rad = collections.Counter()
for line in open(f):
    st, _, n = line.rstrip().rpartition(' '); n = int(n); tot += n
    fr = st.split(';')
    own[fr[-1][:100]] += n
    seen = set()
    for x in fr[1:]:
        k = re.sub(r' \(otp.py:\d+\)', '', x)[:60]
        if k not in seen: fn[k] += n; seen.add(k)
print('samples', tot)
print('--- inclusive (function anywhere on the stack)')
for k, v in fn.most_common(45): print('%5.1f%% %s' % (100.0 * v / tot, k))
print('--- self')
for k, v in own.most_common(20): print('%5.1f%% %s' % (100.0 * v / tot, k))
