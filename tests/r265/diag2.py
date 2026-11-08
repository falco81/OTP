# overload 400/s pw for 20 s, then a 20/s probe on the otp realm for 90 s: how long the daemon takes to recover
import sys, time, threading
sys.argv = ['t_load.py', '1.0.265', '--keep']
import t_load as T
keys, eng, adm = T.setup()
names = lambda suf, a, b: ['zzr265u%05d@%s' % (i, suf) for i in range(a, b)]
ks = lambda l: {n: keys[n] for n in l}
gp, bp = names('r265pw.test', 0, 15000), names('r265pw.test', 15000, 16000)
go, bo = names('r265otp.test', 0, 15000), names('r265otp.test', 15000, 16000)
over = {'kind': 'auth', 'realm': 'pw', 'rate': 400, 'mix': {'fresh': 1}, 'good': gp, 'bad': bp, 'keys': ks(gp + bp)}
probe = {'kind': 'auth', 'realm': 'otp', 'rate': 20, 'mix': {'fresh': 1}, 'good': go, 'bad': bo, 'keys': ks(go + bo)}
res = {}
def p(): res['p'] = T.run('probe', [probe], duration=110)
th = threading.Thread(target=p); th.start()
time.sleep(10)
t_over = time.time()
o = T.run('over', [over], duration=20)
print(T.table([T.lat_line('over', o['rad'][0])]))
th.join()
r = res['p']['rad'][0]
t0 = min(x[0] for x in r['tl'])
b = {}
for t, ms in r['tl']:
    b.setdefault(int((t - t0) // 5), []).append(ms)
for k in sorted(b):
    v = sorted(b[k]); print('t=%3d s (overload %+4.0f s)  n=%3d p50 %7.1f p99 %7.1f max %7.1f' % (k * 5, t0 + k * 5 - t_over, len(v), v[len(v)//2], v[int(len(v)*.99)], v[-1]))
print(T.sys_line('probe', res['p']), r['counts'])
st = adm.get('status'); print(st.get('radius'))
