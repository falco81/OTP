# t_rundir.py VERSION - /run/otp and the API token given back to the pages' group (1.0.232).
# systemd gives a unit's RuntimeDirectory to User:Group (otp:otp) before ExecReload: after
# `systemctl reload otp` the pages could not read the token, /healthz said 503 and the VIP address
# left the node. On the installed daemon here: the group taken away as systemd does, then a SIGHUP
# (as systemctl reload) - and once with no signal at all (the daemon's own round).
# Usage (as root, with the installed daemon, nginx and php-fpm running): python3 t_rundir.py VERSION
import os, sys, time, subprocess, grp, ssl, urllib.request

OK = [0, 0]


def ok(c, w):
    OK[0 if c else 1] += 1
    print(('  ok   ' if c else '  FAIL ') + w)


def health():
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen('https://127.0.0.1/healthz', timeout=5, context=ctx) as r:
            return r.read(200).decode()
    except urllib.error.HTTPError as e:
        return e.read(200).decode()
    except Exception as e:
        return 'error %s' % e


def groups():
    return [grp.getgrgid(os.stat(p).st_gid).gr_name for p in ('/run/otp', '/run/otp/api-token')]


def daemon():
    out = subprocess.run(['pgrep', '-u', 'otp', '-f', 'otp.py --daemon'], capture_output=True, text=True).stdout.split()
    return int(out[-1]) if out else 0


pid = daemon()
ok(pid > 0, 'the daemon runs (%s)' % pid)
ok(health().startswith('ok'), 'healthz ok to begin with')
ok(groups() == ['otp-web', 'otp-web'], 'run dir and token are otp-web: %s' % groups())
for how in ('sighup', 'round'):
    for p in ('/run/otp', '/run/otp/api-token'):
        os.chown(p, -1, grp.getgrnam('otp').gr_gid)          # as systemd does before ExecReload
    ok(health().startswith('down: the pages cannot read'), '%s: the failure reproduced (healthz down)' % how)
    if how == 'sighup':
        os.kill(pid, 1)
        time.sleep(0.5)
    else:
        time.sleep(6.5)
    ok(groups() == ['otp-web', 'otp-web'], '%s: given back to otp-web: %s' % (how, groups()))
    ok(health().startswith('ok'), '%s: healthz ok again' % how)
    ok(daemon() == pid, '%s: the same daemon (no restart)' % how)
st = os.stat('/run/otp/api-token')
ok(oct(st.st_mode & 0o777) == '0o640', 'token mode 0640 (%s)' % oct(st.st_mode & 0o777))
ok(oct(os.stat('/run/otp').st_mode & 0o777) == '0o750', 'run dir mode 0750')
print('== rundir ALL %d / %d' % (OK[0], OK[0] + OK[1]) if not OK[1] else '== rundir FAILED %d of %d' % (OK[1], OK[0] + OK[1]))
sys.exit(1 if OK[1] else 0)
