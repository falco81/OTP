import pexpect, time, pyte
env={'OTP_CONFIG':'/etc/otp/config.json','PATH':'/home/claude/shim:/usr/local/bin:/usr/bin:/bin','TERM':'xterm-old','HOME':'/root','SHELL':'/bin/bash','LANG':'C.UTF-8'}
scr=pyte.Screen(130,30); st=pyte.ByteStream(scr)
c=pexpect.spawn('python3 /usr/local/lib/otp/otp.py --console', env=env, timeout=30, dimensions=(30,130))
def pump(t):
    end=time.time()+t
    while time.time()<end:
        try: st.feed(c.read_nonblocking(65536, timeout=0.2))
        except (pexpect.TIMEOUT, pexpect.EOF): pass
pump(4); print(scr.display[0]); print(scr.display[1][:60])
c.send('\x1b[C\x1b[C'); pump(1); print('right:', scr.display[1][:60])
c.setwinsize(20,90); scr.resize(20,90); pump(1.5); print('resized:', repr(scr.display[0]), repr(scr.display[19]))
c.send('xyzzy-nothing'); pump(1); print(scr.display[0]); print(scr.display[2])
c.send('\x1b'); pump(1); print(scr.display[0])
c.send('\x1b'); pump(2); print(scr.display[0])
c.send('q'); pump(1)
