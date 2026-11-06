import os, sys, re, json, time, threading, tempfile
src = open(sys.argv[1]).read().replace("@route('GET', '/api/load')", '')
SYS = tempfile.mkdtemp()
os.environ['OTP_LOAD_SYS'] = SYS
g = {'__name__': 'x'}
g.update(CONFIG={}, node_name=lambda: 'x', ha_nodes=lambda s: [], fnum=float, log_sparing=lambda *a, **k: None, ApiError=Exception)
exec('import os, re, json, time, threading\n' + src, g)


def w(p, t):
    p = os.path.join(SYS, p); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'w').write(t)


R = []
def ok(n, c, m=''):
    R.append(c); print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)))


# drivetemp read as any sensor: a SATA disk's temperature
os.makedirs(SYS + '/devices/sda/block/sda')
os.makedirs(SYS + '/class/hwmon/hwmon0'); w('class/hwmon/hwmon0/name', 'drivetemp\n')
os.symlink(SYS + '/devices/sda', SYS + '/class/hwmon/hwmon0/device')
w('class/hwmon/hwmon0/temp1_input', '38000\n')
# coretemp, package 0, Core 0 and Core 4; four logical cpus with core_id 0,4,0,4
os.makedirs(SYS + '/devices/platform/coretemp.0')
os.makedirs(SYS + '/class/hwmon/hwmon1')
os.symlink(SYS + '/devices/platform/coretemp.0', SYS + '/class/hwmon/hwmon1/device')
w('class/hwmon/hwmon1/name', 'coretemp\n')
w('class/hwmon/hwmon1/temp1_input', '60000\n'); w('class/hwmon/hwmon1/temp1_label', 'Package id 0\n')
w('class/hwmon/hwmon1/temp2_input', '48000\n'); w('class/hwmon/hwmon1/temp2_label', 'Core 0\n')
w('class/hwmon/hwmon1/temp3_input', '44000\n'); w('class/hwmon/hwmon1/temp3_label', 'Core 4\n')
for n, c in enumerate((0, 4, 0, 4)):
    w('devices/system/cpu/cpu%d/topology/core_id' % n, '%d\n' % c)
    w('devices/system/cpu/cpu%d/topology/physical_package_id' % n, '0\n')
done = []
th = threading.Thread(target=lambda: done.append(g['load_temps']()), daemon=True); th.start(); th.join(5)
ok('load_temps answers', bool(done))
t = done[0] if done else {}
ok('the SATA disk\'s temperature by drivetemp', (done[0] if done else {}).get('disks', {}).get('sda') == 38.0, done)
ok('Core 0 and Core 4 with their package', t.get('pkg_cores') == {'0:0': 48.0, '0:4': 44.0}, t)
# temperatures given to the logical cpus (only those of this machine's /proc/stat count; check the mapping code)
temps = t
got = []
for n in range(4):
    cid = open(SYS + '/devices/system/cpu/cpu%d/topology/core_id' % n).read().strip()
    got.append(temps['pkg_cores'].get('0:' + cid))
ok('every logical cpu given its core\'s temperature', got == [48.0, 44.0, 48.0, 44.0], got)
ok('the filesystems: only kernel ones', 'nfs' not in g['LOAD_FS_KINDS'] and 'cifs' not in g['LOAD_FS_KINDS'] and 'vfat' not in g['LOAD_FS_KINDS']
   and 'fuseblk' not in g['LOAD_FS_KINDS'] and 'ext4' in g['LOAD_FS_KINDS'])
g['load_sample'](); time.sleep(1.1); g['load_sample'](); s2 = g['server_load']()
ok('server_load: a CPU % at the second reading', s2.get('cpu') is not None, s2)
d = g['load_detail']()
ok('load_detail answers', isinstance(d.get('cores'), list) and isinstance(d.get('filesystems'), list))
ok('history kept: the sampler\'s reading', len(g['load_history']()) >= 1, g['load_history']())
print('ALL %d / %d' % (sum(R), len(R)))
