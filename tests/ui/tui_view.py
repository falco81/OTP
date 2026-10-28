import pexpect, time, pyte, sys
env={'OTP_CONFIG':'/etc/otp/config.json','PATH':'/home/claude/shim:/usr/local/bin:/usr/bin:/bin','TERM':'xterm','HOME':'/root','SHELL':'/bin/bash','LANG':'C.UTF-8'}
scr=pyte.Screen(90,24); st=pyte.ByteStream(scr)
c=pexpect.spawn('python3 /usr/local/lib/otp/otp.py --console', env=env, timeout=30, dimensions=(24,90))
def pump(t):
    end=time.time()+t
    while time.time()<end:
        try: st.feed(c.read_nonblocking(65536, timeout=0.2))
        except (pexpect.TIMEOUT, pexpect.EOF): pass
def selrow():
    for i,l in enumerate(scr.display):
        if any(scr.buffer[i][x].bg=='green' for x in range(5,10)): return l.strip()
pump(3); c.send('\x1b[B'); pump(0.4); c.send('\x1bOB'); pump(0.4); print('sel after 2 downs:', selrow())
c.send('\x1b[A'); pump(0.4); print('after up:', selrow())
c.send('\r'); pump(1.5); print('in:', [l.strip() for l in scr.display[3:5]])
c.send('\x1b'); pump(0.8); print('esc ->', [l.strip() for l in scr.display[3:4]])
print('\n'.join(l.rstrip() for l in scr.display))
c.send('q'); pump(1)
