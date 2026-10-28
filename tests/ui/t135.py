import pexpect, time, pyte, sys
env={'OTP_CONFIG':'/etc/otp/config.json','PATH':'/home/claude/shim:/usr/local/bin:/usr/bin:/bin','TERM':__import__('os').environ.get('TT','xterm'),'HOME':'/root','SHELL':'/bin/bash','LANG':'C.UTF-8'}
W,H=int(__import__("os").environ.get("TW","110")),int(__import__("os").environ.get("TH","32"))
scr=pyte.Screen(W,H); st=pyte.ByteStream(scr)
c=pexpect.spawn('python3 /usr/local/lib/otp/otp.py --console', env=env, timeout=30, dimensions=(H,W))
def pump(t):
    end=time.time()+t
    while time.time()<end:
        try: st.feed(c.read_nonblocking(65536, timeout=0.2))
        except (pexpect.TIMEOUT, pexpect.EOF): pass
def show(tag, n=H):
    print('=== '+tag); print('\n'.join(l.rstrip() for l in scr.display[:n] if l.strip()))
def k(s,t=1.2): c.send(s); pump(t)
pump(5); show('start (live log)', 6); print(scr.display[-1])
k('warn',1); show('grep warn', 4)
k('\x1b[5~'); print('after pgup:', scr.display[0][-40:])
k('\x1b'); k('\x1b',2); show('menu',12)
for step in sys.argv[1:]:
    c.send(step.encode().decode('unicode_escape')); pump(2.0); show('after %r'%step)
k('q',1.5)
