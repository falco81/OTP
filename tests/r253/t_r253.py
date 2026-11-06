"""t_r253.py VERSION - 1.0.253: the performance meter's daemon part (its sysfs and its rows of
meta, two nodes in one process); the HA sandbox and the pages: t_ha_perf.py, ui_perf*.js."""
import subprocess, sys, os
here = os.path.dirname(os.path.abspath(__file__))
part = '/home/claude/build/parts/90r_load.py'
total = good = 0
for t in ('t_backend.py', 't_ha_rows.py'):
    out = subprocess.run([sys.executable, os.path.join(here, t), part], capture_output=True, text=True, timeout=300).stdout
    for ln in out.splitlines():
        if ln.startswith(('ok', 'FAIL')):
            total += 1; good += ln.startswith('ok')
            if ln.startswith('FAIL'):
                print(t + ': ' + ln)
print('ALL %d / %d' % (good, total))
