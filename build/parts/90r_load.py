# ---- the performance meter: how busy this node is, in the header of the pages (1.0.253) ----------
# Taken over from the application ai (1.0.72-1.0.76): CPU, memory, the disks, the network - read
# from /proc and /sys only when a page asks (every 3 s while it is shown), nothing running in the
# background; pages asking within the same second share one reading. The details (each core, the
# sensors, each disk and filesystem, each card, the processes taking most) only while a panel is
# open. Off by default (perf_meter); full administrators only - it says what the machine does.
# Each node says its own: in a cluster, the node the page is on.
LOAD_LOCK = threading.Lock()
LOAD_HIST = []                   # the readings of the sampler, one a second, for the graphs (1.0.253)
LOAD_STEP = 1.0                  # how often the sampler reads, while somebody looks
LOAD_HIST_KEEP = 150             # two and a half minutes of them
LOAD_LOOK_S = 10                 # how long an ask keeps the sampler going
LOAD_FS_KINDS = ('ext2', 'ext3', 'ext4', 'xfs', 'btrfs', 'zfs', 'f2fs', 'ntfs3', 'jfs',
                 'reiserfs', 'nilfs2', 'bcachefs')
LOAD_LAST = {'at': 0.0, 'raw': None, 'out': None}


def _load_raw():
    raw = {'at': time.time()}
    try:
        with open('/proc/stat') as f:
            parts = f.readline().split()[1:]
        v = [int(x) for x in parts[:8]] + [0] * (8 - len(parts[:8]))
        raw['cpu_idle'] = v[3] + v[4]
        raw['cpu_all'] = sum(v)
    except (OSError, ValueError):
        pass
    try:
        mem = {}
        with open('/proc/meminfo') as f:
            for line in f:
                k, _s, rest = line.partition(':')
                mem[k] = int(rest.split()[0]) * 1024
        raw['mem_total'] = mem.get('MemTotal', 0)
        raw['mem_used'] = mem.get('MemTotal', 0) - mem.get('MemAvailable', mem.get('MemFree', 0))
        raw['swap_used'] = mem.get('SwapTotal', 0) - mem.get('SwapFree', 0)
    except (OSError, ValueError, IndexError):
        pass
    try:
        rd = wr = 0
        whole = set(os.listdir('/sys/block'))
        with open('/proc/diskstats') as f:
            for line in f:
                x = line.split()
                # whole disks only (a partition is in its disk's numbers already),
                # no loop devices, no RAM disks, no device-mapper twice over
                if len(x) < 10 or x[2] not in whole or x[2].startswith(('loop', 'ram', 'dm-', 'zram', 'sr')):
                    continue
                rd += int(x[5]) * 512
                wr += int(x[9]) * 512
        raw['disk_rd'], raw['disk_wr'] = rd, wr
    except (OSError, ValueError):
        pass
    try:
        rx = tx = 0
        with open('/proc/net/dev') as f:
            for line in f.readlines()[2:]:
                name, _s, rest = line.partition(':')
                name = name.strip()
                # the cards, not the loopback nor the bridges and pairs of containers
                if not load_nic_counted(name):
                    continue
                x = rest.split()
                rx += int(x[0])
                tx += int(x[8])
        raw['net_rx'], raw['net_tx'] = rx, tx
    except (OSError, ValueError, IndexError):
        pass
    return raw


LOAD_SYS = os.environ.get('OTP_LOAD_SYS') or '/sys'     # the tests point it at a sysfs of their own
LOAD_DETAIL = {'at': 0.0, 'raw': None, 'out': None}


def load_nic_counted(name):
    """A network card counted: not the loopback, not the bridges and pairs of
    containers, not a card that is a slave of a bond (the bond is counted)."""
    if name == 'lo' or name.startswith(('veth', 'docker', 'br-', 'virbr', 'podman', 'cni', 'flannel', 'tun', 'tap',
                                       'vnet', 'ifb', 'dummy', 'lxc', 'kube', 'cali', 'vxlan', 'genev')):
        return False
    master = os.path.join(LOAD_SYS, 'class/net', name, 'master')
    if os.path.islink(master) and os.path.isdir(os.path.join(os.path.realpath(master), 'bonding')):
        return False
    return True


def _load_read(path, default=''):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def load_temps():
    """What the sensors say: {'cpu': [(label, °C)], 'cores': {core n: °C}, 'disks': {name: °C}, 'other': [...]}.
    hwmon first (coretemp, k10temp, zenpower, nvme, drivetemp, acpitz...), then the thermal zones."""
    out = {'cpu': [], 'cores': {}, 'pkg_cores': {}, 'disks': {}, 'other': []}
    base = os.path.join(LOAD_SYS, 'class/hwmon')
    try:
        mons = sorted(os.listdir(base))
    except OSError:
        mons = []
    for m in mons:
        d = os.path.join(base, m)
        chip = _load_read(os.path.join(d, 'name'))
        try:
            files = sorted(f for f in os.listdir(d) if re.match(r'^temp\d+_input$', f))
        except OSError:
            continue
        for f in files:
            n = f.split('_')[0]
            try:
                t = int(_load_read(os.path.join(d, f), 'x')) / 1000.0
            except ValueError:
                continue
            if t <= -40 or t > 150:
                continue
            label = _load_read(os.path.join(d, n + '_label')) or chip
            core = re.match(r'^Core (\d+)$', label)
            if chip in ('coretemp', 'k10temp', 'zenpower', 'cpu_thermal', 'soc_thermal', 'k8temp', 'via_cputemp'):
                if core:
                    out['cores'][int(core.group(1))] = round(t, 1)
                    # With its package (coretemp.P): two packages each have a Core 0.
                    pkg = re.search(r'\.(\d+)$', os.path.realpath(os.path.join(d, 'device')))
                    out['pkg_cores']['%s:%s' % (pkg.group(1) if pkg else '0', core.group(1))] = round(t, 1)
                else:
                    out['cpu'].append([label, round(t, 1)])
            elif chip in ('nvme', 'drivetemp'):
                dev = ''
                try:
                    dev = os.path.basename(os.path.realpath(os.path.join(d, 'device')))
                except OSError:
                    pass
                if chip == 'nvme':
                    try:
                        nv = [x for x in os.listdir(os.path.join(d, 'device')) if re.match(r'^nvme\d+n\d+$', x)]
                        dev = nv[0] if nv else dev
                    except OSError:
                        pass
                elif chip == 'drivetemp':
                    try:
                        blk = os.listdir(os.path.join(d, 'device', 'block'))
                        dev = blk[0] if blk else dev
                    except OSError:
                        pass
                if label.lower() in ('composite', chip, '') or dev not in out['disks']:
                    out['disks'][dev or chip] = round(t, 1)
            else:
                out['other'].append([chip + (' ' + label if label != chip else ''), round(t, 1)])
    if not out['cpu'] and not out['cores']:
        tz = os.path.join(LOAD_SYS, 'class/thermal')
        try:
            zones = sorted(z for z in os.listdir(tz) if z.startswith('thermal_zone'))
        except OSError:
            zones = []
        for z in zones:
            kind = _load_read(os.path.join(tz, z, 'type'))
            try:
                t = int(_load_read(os.path.join(tz, z, 'temp'), 'x')) / 1000.0
            except ValueError:
                continue
            if -40 < t < 150:
                (out['cpu'] if re.search(r'cpu|x86_pkg|soc|core', kind, re.I) else out['other']).append(
                    [kind, round(t, 1)])
    return out


def _load_detail_raw():
    raw = {'at': time.time(), 'cores': {}, 'disks': {}, 'nics': {}, 'procs': {}}
    try:
        with open('/proc/stat') as f:
            for line in f:
                m = re.match(r'^cpu(\d+)\s+(.*)$', line)
                if m:
                    v = [int(x) for x in m.group(2).split()[:8]]
                    raw['cores'][int(m.group(1))] = (v[3] + v[4], sum(v))
    except (OSError, ValueError):
        pass
    try:
        whole = set(os.listdir(os.path.join(LOAD_SYS, 'block')))
        with open('/proc/diskstats') as f:
            for line in f:
                x = line.split()
                if len(x) < 13 or x[2] not in whole or x[2].startswith(('loop', 'ram', 'zram', 'sr')):
                    continue
                raw['disks'][x[2]] = (int(x[5]) * 512, int(x[9]) * 512, int(x[12]))
    except (OSError, ValueError):
        pass
    try:
        with open('/proc/net/dev') as f:
            for line in f.readlines()[2:]:
                name, _s, rest = line.partition(':')
                name = name.strip()
                if load_nic_counted(name):
                    x = rest.split()
                    raw['nics'][name] = (int(x[0]), int(x[8]))
    except (OSError, ValueError, IndexError):
        pass
    tick = os.sysconf('SC_CLK_TCK') if hasattr(os, 'sysconf') else 100
    page = os.sysconf('SC_PAGE_SIZE') if hasattr(os, 'sysconf') else 4096
    try:
        pids = [p for p in os.listdir('/proc') if p.isdigit()]
    except OSError:
        pids = []
    for pid in pids:
        try:
            with open('/proc/%s/stat' % pid) as f:
                st = f.read()
            name = st[st.index('(') + 1:st.rindex(')')]
            rest = st[st.rindex(')') + 2:].split()
            raw['procs'][int(pid)] = (name[:40], (int(rest[11]) + int(rest[12])) / float(tick), int(rest[21]) * page)
        except (OSError, ValueError, IndexError):
            continue
    return raw


def load_detail():
    """What the header's panels show when opened: each core, its frequency and
    temperature, the disks one by one and the filesystems, the cards one by one,
    the processes taking most - read only while a panel is open."""
    with LOAD_LOCK:
        now = time.time()
        if LOAD_DETAIL['out'] and now - LOAD_DETAIL['at'] < 1.0:
            return LOAD_DETAIL['out']
        raw = _load_detail_raw()
        was = LOAD_DETAIL['raw'] or {}
        if not was or now - was.get('at', 0) > 30:
            # the first look (or one long after the last): two readings a
            # moment apart, so the panel opens with numbers, not dots
            was = raw
            time.sleep(0.3)
            raw = _load_detail_raw()
        dt = max(0.2, raw['at'] - was.get('at', raw['at'] - 1)) if was else None
        temps = load_temps()
        cores = []
        for n in sorted(raw['cores']):
            idle, allc = raw['cores'][n]
            busy = None
            if dt and n in was.get('cores', {}):
                pi, pa = was['cores'][n]
                if allc > pa:
                    busy = round(max(0.0, min(1.0, 1 - (idle - pi) / float(allc - pa))) * 100, 1)
            mhz = _load_read(os.path.join(LOAD_SYS, 'devices/system/cpu/cpu%d/cpufreq/scaling_cur_freq' % n))
            # The temperature of the core this logical processor is a thread of (its topology):
            # by the number of cpuN, half of them had none with hyperthreading, and others with
            # core numbers that leave gaps (Core 0, 1, 4, 5...).
            topo = os.path.join(LOAD_SYS, 'devices/system/cpu/cpu%d/topology' % n)
            cid = _load_read(os.path.join(topo, 'core_id'))
            pkg = _load_read(os.path.join(topo, 'physical_package_id'), '0')
            temp = None
            if cid.isdigit():
                temp = temps['pkg_cores'].get('%s:%s' % (pkg if pkg.isdigit() else '0', cid))
                if temp is None:
                    temp = temps['cores'].get(int(cid))
            else:
                temp = temps['cores'].get(n)
            cores.append({'n': n, 'busy': busy, 'mhz': round(int(mhz) / 1000) if mhz.isdigit() else None,
                          'temp': temp})
        if cores and not any(c['mhz'] for c in cores):
            try:
                with open('/proc/cpuinfo') as f:
                    mh = [float(x.split(':')[1]) for x in f if x.startswith('cpu MHz')]
                for c, m in zip(cores, mh):
                    c['mhz'] = round(m)
            except (OSError, ValueError, IndexError):
                pass
        model = ''
        try:
            with open('/proc/cpuinfo') as f:
                for line in f:
                    if line.startswith(('model name', 'Hardware', 'Model')):
                        model = line.split(':', 1)[1].strip()
                        break
        except OSError:
            pass
        disks = []
        for name, (rd, wr, ms) in sorted(raw['disks'].items()):
            one = {'name': name, 'temp': temps['disks'].get(name),
                   'size': int(_load_read(os.path.join(LOAD_SYS, 'block', name, 'size'), '0') or 0) * 512,
                   'model': _load_read(os.path.join(LOAD_SYS, 'block', name, 'device/model'))}
            if dt and name in was.get('disks', {}):
                prd, pwr, pms = was['disks'][name]
                one['rd'] = max(0, round((rd - prd) / dt))
                one['wr'] = max(0, round((wr - pwr) / dt))
                one['util'] = round(max(0.0, min(100.0, (ms - pms) / (dt * 10.0))), 1)
            disks.append(one)
        fss = []
        seen = set()
        try:
            with open('/proc/mounts') as f:
                for line in f:
                    dev, mnt, kind = line.split()[:3]
                    if kind in ('proc', 'sysfs', 'tmpfs', 'devtmpfs', 'devpts', 'cgroup', 'cgroup2', 'overlay',
                                'squashfs', 'mqueue', 'debugfs', 'tracefs', 'securityfs', 'pstore', 'bpf', 'autofs',
                                'fusectl', 'configfs', 'hugetlbfs', 'binfmt_misc', 'efivarfs', 'nsfs', 'ramfs',
                                'rpc_pipefs', 'selinuxfs', 'fuse.lxcfs', 'iso9660') or dev in seen:
                        continue
                    # Only the kernel's own filesystems on this machine's disks: never FUSE nor a
                    # network share - statvfs hangs on a server away, under LOAD_LOCK, and every
                    # /api/load with it - nor FAT (its free space is counted over the whole table).
                    if kind not in LOAD_FS_KINDS:
                        continue
                    if not dev.startswith('/') and kind not in ('zfs', 'btrfs'):
                        continue
                    seen.add(dev)
                    try:
                        sv = os.statvfs(mnt)
                    except OSError:
                        continue
                    total = sv.f_blocks * sv.f_frsize
                    if not total:
                        continue
                    free = sv.f_bavail * sv.f_frsize
                    fss.append({'mount': mnt, 'dev': dev, 'kind': kind, 'total': total, 'used': total - sv.f_bfree * sv.f_frsize,
                                'free': free})
        except OSError:
            pass
        nics = []
        for name, (rx, tx) in sorted(raw['nics'].items()):
            sp = _load_read(os.path.join(LOAD_SYS, 'class/net', name, 'speed'))
            one = {'name': name, 'state': _load_read(os.path.join(LOAD_SYS, 'class/net', name, 'operstate')),
                   'speed': int(sp) if sp.lstrip('-').isdigit() and int(sp) > 0 else None, 'rx_all': rx, 'tx_all': tx}
            if dt and name in was.get('nics', {}):
                one['rx'] = max(0, round((rx - was['nics'][name][0]) / dt))
                one['tx'] = max(0, round((tx - was['nics'][name][1]) / dt))
            nics.append(one)
        procs = []
        for pid, (name, cpu_s, rss) in raw['procs'].items():
            p = {'pid': pid, 'name': name, 'rss': rss}
            if dt and pid in was.get('procs', {}):
                p['cpu'] = round(max(0.0, (cpu_s - was['procs'][pid][1]) / dt) * 100, 1)
            procs.append(p)
        mem = {}
        try:
            with open('/proc/meminfo') as f:
                for line in f:
                    k, _s, rest = line.partition(':')
                    mem[k] = int(rest.split()[0]) * 1024
        except (OSError, ValueError, IndexError):
            pass
        up = 0.0
        try:
            up = float(_load_read('/proc/uptime', '0').split()[0])
        except ValueError:
            pass
        out = {'cores': cores, 'model': model, 'temps': temps, 'disks': disks, 'filesystems': fss, 'nics': nics,
               'top_cpu': sorted([p for p in procs if p.get('cpu')], key=lambda p: -p['cpu'])[:6],
               'top_mem': sorted(procs, key=lambda p: -p['rss'])[:6], 'uptime': up,
               'mem': {k: mem.get(v) for k, v in (('total', 'MemTotal'), ('available', 'MemAvailable'),
                                                  ('cached', 'Cached'), ('buffers', 'Buffers'),
                                                  ('swap_total', 'SwapTotal'), ('swap_free', 'SwapFree'),
                                                  ('shared', 'Shmem'))},
               'procs': len(procs)}
        LOAD_DETAIL.update(at=now, raw=raw, out=out)
        return out


def server_load(fresh=False):
    """{cpu %, mem used/total, disk read/write B/s, net in/out B/s, load}."""
    with LOAD_LOCK:
        now = time.time()
        if not fresh and LOAD_LAST['out'] and now - LOAD_LAST['at'] < 1.0:
            return LOAD_LAST['out']
        raw = _load_raw()
        was = LOAD_LAST['raw']
        out = {'at': now, 'cores': os.cpu_count() or 1, 'mem_total': raw.get('mem_total'),
               'mem_used': raw.get('mem_used'), 'swap_used': raw.get('swap_used')}
        try:
            out['load'] = [round(x, 2) for x in os.getloadavg()]
        except OSError:
            out['load'] = None
        if was:
            dt = max(0.2, raw['at'] - was['at'])

            def rate(k):
                if k in raw and k in was and raw[k] >= was[k]:
                    return round((raw[k] - was[k]) / dt)
                return None
            if raw.get('cpu_all') and was.get('cpu_all') and raw['cpu_all'] > was['cpu_all']:
                busy = 1 - (raw['cpu_idle'] - was['cpu_idle']) / float(raw['cpu_all'] - was['cpu_all'])
                out['cpu'] = round(max(0.0, min(1.0, busy)) * 100, 1)
            for k in ('disk_rd', 'disk_wr', 'net_rx', 'net_tx'):
                out[k] = rate(k)
            out['over_s'] = round(dt, 1)
        LOAD_LAST.update(at=now, raw=raw, out=out)
        return out


LOAD_BACK_S = 5                  # a reading older than the last by more: the clock was stepped back (1.0.255)


def load_history(since=None, span=150):
    """The sampler's readings newer than `since` (this node's clock), oldest first."""
    now = time.time()
    if since is not None and since > now + 1:
        since = None                # a page's since later than now: this clock was stepped back (1.0.255)
    with LOAD_LOCK:
        return [dict(x) for x in LOAD_HIST if now - x['at'] <= span
                and (since is None or x['at'] > since)]


# The sampler (1.0.253): one reading a second, at an even pace, while a page looks (an ask
# keeps it going LOAD_LOOK_S) - so the graphs are drawn from readings a second apart whoever
# asks how often, two tabs or one. Nobody looking: it waits and reads nothing.
LOAD_WAKE = threading.Event()
LOAD_LOOK = {'until': 0.0, 'other': 0.0}


LOAD_HA_WAKE = threading.Event()


def load_ask():
    """A page on this node looks."""
    if time.monotonic() >= LOAD_LOOK['until']:
        LOAD_HA_WAKE.set()          # just begun: its row written now, not in 5 s
        LOAD_LOOK['began'] = time.monotonic()
    LOAD_LOOK['until'] = time.monotonic() + LOAD_LOOK_S
    LOAD_WAKE.set()


def load_keep():
    """The other node's page looks: the sampler kept going until the next row (no 'asked')."""
    LOAD_LOOK['other'] = time.monotonic() + LOAD_PUB_S + 2
    LOAD_WAKE.set()


def load_looked():
    now = time.monotonic()
    return (now < LOAD_LOOK['until'] or now < LOAD_LOOK['other']) and bool(CONFIG.get('perf_meter'))


def load_sample():
    out = server_load(fresh=True)
    if out.get('cpu') is None:
        return
    mp = 100.0 * out['mem_used'] / out['mem_total'] if out.get('mem_total') else None
    one = {'at': round(out['at'], 2), 'cpu': out.get('cpu'), 'mem': round(mp, 1) if mp is not None else None}
    for k in ('disk_rd', 'disk_wr', 'net_rx', 'net_tx'):
        one[k] = out.get(k) or 0
    with LOAD_LOCK:
        # the clock stepped back (1.0.255): the readings before it would stand in the future of
        # every new one - the history starts again
        if LOAD_HIST and one['at'] < LOAD_HIST[-1]['at'] - LOAD_BACK_S:
            del LOAD_HIST[:]
        LOAD_HIST.append(one)
        del LOAD_HIST[:-LOAD_HIST_KEEP]


def load_sampler(daemon):
    while not daemon.stop_flag.is_set():
        if not load_looked():
            LOAD_WAKE.clear()           # cleared before the second look: an ask between is not lost
            if not load_looked():
                LOAD_WAKE.wait(5)
            if not load_looked():
                continue
            # a pause: the first reading after it only starts the count again
            with LOAD_LOCK:
                LOAD_LAST.update(at=0.0, raw=None, out=None)
        began = time.monotonic()
        try:
            load_sample()
        except Exception as e:                          # noqa: BLE001
            log_sparing('load-sample', 'the performance meter: %s' % e, 'warn', every=600)
        daemon.stop_flag.wait(max(0.05, LOAD_STEP - (time.monotonic() - began)))


# Both nodes of a cluster (1.0.253): one small row of meta for each node, load:<node>, written
# every LOAD_PUB_S only while the meter is looked at - its readings of the last seconds (one a
# second, so the other node's graph is as smooth as this one's) and its numbers now. A node
# whose page is open says so in its row ('asked'); the other node, seeing such a row change,
# samples and writes too, for LOAD_WANTED_S after the last change (its own clock: the nodes'
# clocks are never compared). The page closed: its node stops within LOAD_LOOK_S, the other
# within LOAD_WANTED_S. Standalone, or the meter off: no row is read or written.
LOAD_PUB_S = 5
LOAD_WANTED_S = 22
LOAD_STALE_S = 15
LOAD_HA = {'seen': {}, 'wanted': 0.0, 'mine': False, 'ticked': False, 'peers': {}}
LOAD_HA_LOCK = threading.Lock()


def load_cluster(store):
    """The other nodes of this node's cluster ([] standalone)."""
    if not CONFIG.get('ha_mode'):
        return []
    try:
        return [n for n in ha_nodes(store) if not n.get('me')]
    except Exception:                                   # noqa: BLE001
        return []


def load_drop_own(store):
    try:
        store.db.run('DELETE FROM meta WHERE k = ?', ('load:' + node_name(),))
    except Exception:                                   # noqa: BLE001
        pass
    with LOAD_HA_LOCK:
        LOAD_HA.update(mine=False, wanted=0.0, ticked=False)
        LOAD_HA['seen'].clear()
        LOAD_HA['peers'].clear()


def load_ha_tick(store):
    """Every LOAD_PUB_S: the other nodes' rows read, this node's written - while looked at."""
    peers = load_cluster(store) if CONFIG.get('perf_meter') else []
    if not peers:
        if LOAD_HA['mine']:
            load_drop_own(store)
        return
    me, mono = node_name(), time.monotonic()
    here = time.monotonic() < LOAD_LOOK['until']        # a page on this node looks
    names = set(n['name'] for n in peers)
    rows = store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'load:%'")
    with LOAD_HA_LOCK:
        for r in rows:
            name = str(r['k'])[len('load:'):]
            if name not in names:
                continue
            was = LOAD_HA['seen'].get(name)
            if was == r['v']:
                continue
            LOAD_HA['seen'][name] = r['v']
            try:
                d = json.loads(r['v'] or '{}')
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            # a row come or changed since the last look (not at the first: it may be old)
            if (was is not None or LOAD_HA['ticked']) and d.get('asked'):
                LOAD_HA['wanted'] = mono
            one = LOAD_HA['peers'].setdefault(name, {'hist': [], 'now': None, 'at': 0.0})
            if was is None and not LOAD_HA['ticked']:
                continue
            last = one['hist'][-1]['at'] if one['hist'] else 0
            fine = [x for x in d.get('hist') or [] if isinstance(x, dict) and isinstance(x.get('at'), (int, float))]
            if fine and last and max(x['at'] for x in fine) < last - LOAD_BACK_S:
                # that node's clock stepped back (1.0.255): what it had said before goes, or
                # nothing it says would ever be newer than its last
                one['hist'], last = [], 0
            got = [x for x in fine if x['at'] > last]
            one['hist'] = (one['hist'] + got)[-LOAD_HIST_KEEP:]
            one['now'] = d.get('now') if isinstance(d.get('now'), dict) else None
            one['at'] = mono
        LOAD_HA['ticked'] = True
        wanted = mono - LOAD_HA['wanted'] < LOAD_WANTED_S if LOAD_HA['wanted'] else False
    if not here and not wanted:
        return
    if not here:
        load_keep()                 # the other node's page keeps this sampler going
    d = {'asked': here, 'now': load_now(), 'hist': load_history(time.time() - LOAD_PUB_S - 3)}
    store.set_meta('load:' + me, json.dumps(d, separators=(',', ':')))
    LOAD_HA['mine'] = True


def load_ha_watch(daemon):
    """The thread of load_ha_tick. Off, standalone, nobody looking: CONFIG only, nothing read."""
    while not daemon.stop_flag.is_set():
        LOAD_HA_WAKE.wait(LOAD_PUB_S)
        LOAD_HA_WAKE.clear()
        if daemon.stop_flag.is_set():
            break
        if not LOAD_HA['mine']:
            if not CONFIG.get('perf_meter') or not CONFIG.get('ha_mode'):
                continue
            # nobody looking here and nothing heard: one look at the rows every 10 s, for a
            # page opened on the other node
            if time.monotonic() >= LOAD_LOOK['until'] and \
                    time.monotonic() - LOAD_HA.get('looked', 0) < 10:
                continue
        LOAD_HA['looked'] = time.monotonic()
        try:
            load_ha_tick(daemon.store)
        except Exception as e:                          # noqa: BLE001
            log_sparing('load-ha', 'the performance meter of the other node: %s' % e, 'warn', every=600)


def load_others(store, since):
    out = []
    for n in load_cluster(store):
        with LOAD_HA_LOCK:
            got = dict(LOAD_HA['peers'].get(n['name']) or {})
        # Not late while the other node is only waking up to a page that began to look (1.0.257):
        # its last numbers shown at once, the graph going on from its next row - "does not
        # answer" was said for the first seconds of every look.
        waking = time.monotonic() - LOAD_LOOK.get('began', 0.0) < LOAD_STALE_S + LOAD_PUB_S
        late = not got.get('at') or (time.monotonic() - got['at'] > LOAD_STALE_S and
                                     not (waking and got.get('now')))
        hist = got.get('hist') or []
        after = since.get(n['name']) or 0
        if hist and after > hist[-1]['at'] + LOAD_BACK_S:
            after = 0               # a since later than all it said: that node's clock stepped back (1.0.255)
        out.append({'node': n['name'], 'late': late, 'now': got.get('now'),
                    'hist': [x for x in hist if x['at'] > after]})
    return out


def load_since(text):
    """since=a:1793911827.1,b:... - each node's own clock, as its readings carry it."""
    out = {}
    for part in str(text or '').split(',')[:8]:
        name, _, t = part.rpartition(':')
        try:
            out[name] = float(t)
        except ValueError:
            continue
    return out


def load_now():
    d = dict(server_load())
    return {k: d.get(k) for k in ('at', 'cpu', 'cores', 'mem_total', 'mem_used', 'swap_used', 'load',
                                  'disk_rd', 'disk_wr', 'net_rx', 'net_tx', 'over_s')}


@route('GET', '/api/load')
def _load(h):
    """The performance meter (1.0.253): this node's readings newer than since (at the first
    look - F5 too - all of the last two and a half minutes), its numbers now, with detail=1 the
    panels' details; in a cluster the other nodes' as last heard."""
    h.me('fulladmin')
    if not CONFIG.get('perf_meter'):
        raise ApiError(404, 'the performance meter is switched off (Settings - About)')
    load_ask()
    since = load_since(h.arg('since'))
    me = node_name()
    out = {'node': me, 'now': load_now(), 'step': LOAD_STEP, 'hist': load_history(since.get(me))}
    if h.arg('detail'):
        out['detail'] = load_detail()
    if CONFIG.get('ha_mode'):
        out['others'] = load_others(h.store, since)
    return out
