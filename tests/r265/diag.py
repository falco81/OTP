# diag.py WHAT SECONDS: a phase of t_load.py alone, with py-spy on the daemon (collapsed stacks to out/spy-WHAT.txt)
import sys, subprocess, time, collections
what, secs = sys.argv[1], int(sys.argv[2])
http = int(sys.argv[3]) if len(sys.argv) > 3 else None
sys.argv = ['t_load.py', '1.0.265', '--keep']
import t_load as T
keys, eng, adm = T.setup(); T.ADM.append(adm)
names = lambda suf, a, b: ['zzr265u%05d@%s' % (i, suf) for i in range(a, b)]
ks = lambda l: {n: keys[n] for n in l}
gp, bp = names('r265pw.test', 0, 15000), names('r265pw.test', 15000, 16000)
go, bo = names('r265otp.test', 0, 15000), names('r265otp.test', 15000, 16000)
ch = names('r265ch.test', 0, 2000)
def auth(realm, rate, mix, g, b): return {'kind': 'auth', 'realm': realm, 'rate': rate, 'mix': mix, 'good': g, 'bad': b, 'keys': ks(g + b)}
S = {'Mpw': [auth('pw', 100, {'fresh': .7, 'wrong': .2, 'replay': .1}, gp, bp)],
     'Macct': [auth('pw', 100, {'fresh': 1}, gp, bp), {'kind': 'acct', 'realm': 'acct', 'rate': 300, 'nsock': 8}],
     'Mall': [auth('pw', 100, {'fresh': .7, 'wrong': .2, 'replay': .1}, gp, bp), {'kind': 'chal', 'realm': 'ch', 'rate': 10, 'good': ch, 'keys': ks(ch)},
              {'kind': 'acct', 'realm': 'acct', 'rate': 300, 'nsock': 8}],
     'Bpw': [auth('pw', 140, {'fresh': .9, 'wrong': .1}, gp, bp)],
     'Botp': [auth('otp', 140, {'fresh': .9, 'wrong': .1}, go, bo)]}

pid = T.pids()['daemon']
spy = subprocess.Popen(['py-spy', 'record', '--nonblocking'] + (['--gil'] if __import__('os').environ.get('GIL') else []) + ['-p', str(pid), '-d', str(secs - 2), '-r', '200', '-f', 'raw', '-t', '-o',
                        'out/spy-%s.txt' % what], stdout=subprocess.DEVNULL, stderr=open('out/spy.err', 'w'))
o = T.run(what, S[what], http=http, duration=secs)
spy.wait()
for r in o['rad']:
    print(T.table([T.lat_line(what, r, w) for w in ['all'] + sorted(k for k in r['lat'] if k != 'all')]))
print(T.sys_line(what, o))
if http: T.http_report(what, o)
# where the slow ones were: latency by second
for r in o['rad']:
    if r['kind'] != 'auth': continue
print(T.classify_rejects(o['rad'][0], time.time() - secs - 30))
