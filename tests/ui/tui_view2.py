import pexpect, time, pyte
env={'OTP_CONFIG':'/etc/otp/config.json','PATH':'/home/claude/shim:/usr/local/bin:/usr/bin:/bin','TERM':'xterm','HOME':'/root','SHELL':'/bin/bash','LANG':'C.UTF-8'}
scr=pyte.Screen(100,30); st=pyte.ByteStream(scr)
c=pexpect.spawn('python3 /usr/local/lib/otp/otp.py --console', env=env, timeout=30, dimensions=(30,100))
def pump(t):
    end=time.time()+t
    while time.time()<end:
        try: st.feed(c.read_nonblocking(65536, timeout=0.2))
        except (pexpect.TIMEOUT, pexpect.EOF): pass
pump(4); print('\n'.join(l.rstrip() for l in scr.display[:6]))
c.send('4'); pump(1); c.send('\r'); pump(1); c.send('\r'); pump(3); c.send('\x1b'); pump(1.5)
c.send('\r'); pump(1.5); print('--- prompt screen:'); print('\n'.join(l.rstrip() for l in scr.display[:5]))
c.send('\x1b'); pump(1); c.send('q'); pump(1)
