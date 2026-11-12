#!/usr/bin/python3 -I
"""otp_web.py - the web side of a node, put in place by root (1.0.47).

Two things the pages may ask for that need root, both about HTTPS:

  * TLS - the certificate (with its chain, and the root it is checked
    against), the protocols, the ciphers and the DH parameters nginx uses:
    for this node's own name, and for the cluster's web address;
  * the cluster's web address (VIP): one more address the pages and the
    administration answer on, on one node at a time - active/standby - held
    by keepalived (VRRP). otp writes /run/otp/vip-state every few seconds
    and keepalived asks /usr/libexec/keepalived/otp-vip-check whether this node
    may hold it (otp answering, not in maintenance, not being upgraded) and
    whether it is the one preferred; it moves the address by itself when
    that changes, or when the other node is gone. RADIUS never uses it:
    both nodes go on answering RADIUS on their own addresses.

The daemon runs as `otp` and may not do any of this: it lays a request down
in /var/lib/otp/web/request.json and systemd (otp-web.path) starts this as
root. Nothing in the request is trusted: every value is checked against the
one shape it may have before it goes into a file, certificates and keys are
read by openssl, nginx is asked (nginx -t) before it is reloaded and put
back as it was when it says no, and the folder is used through one
descriptor, never a path the otp account could swap for a link.

  otp_web.py            serve request.json (as root, from systemd)
  otp_web.py --status   what is in place here (JSON)
  otp_web.py --os-job ID check|upgrade   the system's updates (started by itself)
  otp_web.py --sshd-back                 a change of sshd on trial put back (its timer)
"""
import base64
import errno
import hashlib
import io
import ipaddress
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import select
import signal
import tarfile
import tempfile
import time

STATE_DIR = os.environ.get('OTP_STATE', '/var/lib/otp')
WEB_DIR = os.path.join(STATE_DIR, 'web')
KA_CONF = os.environ.get('OTP_VIP_KA_CONF', '/etc/keepalived/keepalived.conf')
NGINX_DIR = os.environ.get('OTP_VIP_NGINX_DIR', '/etc/nginx/conf.d')
NGINX_MAIN = os.path.join(NGINX_DIR, 'otp.conf')
NGINX_VIP = os.path.join(NGINX_DIR, 'otp_vip.conf')   # read after otp.conf: never the default server
# The balancer's own port (1.0.259): read after otp.conf too - its limits are defined there.
NGINX_LB = os.path.join(NGINX_DIR, 'otp_lbport.conf')
CERT_DIR = os.environ.get('OTP_VIP_CERT_DIR', '/etc/nginx/certs')
# Where SELinux lets keepalived run it; the program's own folder otherwise.
CHECK = os.environ.get('OTP_VIP_CHECK') or next(
    (p for p in ('/usr/libexec/keepalived/otp-vip-check', '/usr/local/lib/otp/otp-vip-check')
     if os.access(p, os.X_OK)), '/usr/libexec/keepalived/otp-vip-check')
NO_SERVICES = bool(os.environ.get('OTP_VIP_NO_SERVICES'))      # tests: no systemctl
PGLOG_ASK = 'pglog.ask'
PGTLS_ASK = 'pgtls.ask'          # the link between the two databases (1.0.104)
PGTLS_FILE = 'pgtls.json'
HA_CA_FILE = os.environ.get('OTP_HA_CA', '/etc/pki/otp/ha-ca.pem')
PG_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,62}\Z')
PG_HBA_WORDS = ('all', 'sameuser', 'samerole', 'samegroup', 'replication')
PGLOG_FILE = 'pglog.json'
PG_PW_RE = re.compile(r"(?i)(password\s*=\s*)('(?:[^']|'')*'|\S+)")
MARK = '# written by otp (otp_web.py) - otp keeps this file; change it on its pages'


ADDR_RE = re.compile(r'^[0-9A-Fa-f:.]+(/[0-9]{1,3})?\Z')


def plain(text, how):
    """An address, a network or an address with its prefix - and nothing
    else (1.0.57): ipaddress keeps an IPv6 scope id (fe80::1%eth0) with any
    character in it, newlines and braces included, and so into nginx,
    keepalived and ip6tables files root writes."""
    text = str(text or '').strip()
    if not ADDR_RE.match(text):
        raise ValueError('not a plain address')
    got = {'address': ipaddress.ip_address, 'network': lambda t: ipaddress.ip_network(t, strict=False),
           'interface': ipaddress.ip_interface}[how](text)
    if '%' in str(got):
        raise ValueError('a scope id is not taken')
    return got


class Refused(Exception):
    pass


# ---- the folder the otp account owns: one descriptor, never a path -----------------
FD = [None]


def web_fd():
    if FD[0] is None:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        top = os.open(STATE_DIR, flags)
        try:
            FD[0] = os.open('web', flags, dir_fd=top)
        finally:
            os.close(top)
    return FD[0]


def read_req(name, most=262144):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=web_fd())
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise Refused('%s is not a file' % name)
        data = os.read(fd, most + 1)
    finally:
        os.close(fd)
    if len(data) > most:
        raise Refused('the request is far bigger than any address needs')
    return data


def write_here(name, text):
    d = web_fd()
    tmp = '.%s.%d' % (name, os.getpid())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640, dir_fd=d)
    with os.fdopen(fd, 'w') as f:
        f.write(text)
        try:
            import grp
            os.fchown(f.fileno(), 0, grp.getgrnam('otp').gr_gid)
        except (KeyError, OSError):
            pass
    os.replace(tmp, name, src_dir_fd=d, dst_dir_fd=d)


def write_here_bytes(name, data):
    """write_here for bytes: in the folder opened at the start, never by its path - the service
    owns the folder above it and could have put a link in its place meanwhile."""
    d = web_fd()
    tmp = '.%s.%d' % (name, os.getpid())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640, dir_fd=d)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            try:
                import grp
                os.fchown(f.fileno(), 0, grp.getgrnam('otp').gr_gid)
            except (KeyError, OSError):
                pass
        os.replace(tmp, name, src_dir_fd=d, dst_dir_fd=d)
    except BaseException:
        try:
            os.unlink(tmp, dir_fd=d)
        except OSError:
            pass
        raise


def write_root(path, text, mode):
    """A file of root's, replaced whole."""
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.otp-', dir=folder)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(text)
            f.flush()
            os.fchmod(f.fileno(), mode)        # the file itself, never a link (1.0.205)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def pg_file_put(path, text, mode, uid=None, gid=None):
    """A file in a folder of PostgreSQL's, replaced whole (1.0.149): written
    to a new file of an unguessable name, its mode and owner set on the open
    file, then renamed over - never a name followed, which whoever runs as
    postgres could have made a link to a file of root's."""
    folder = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix='.otp-', dir=folder)
    try:
        os.fchmod(fd, mode)
        if uid is not None:
            os.fchown(fd, uid, gid if gid is not None else -1)
        with os.fdopen(fd, 'w') as f:
            fd = None
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def pg_file_read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'r') as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise Refused('%s is not a plain file' % path)
        return f.read()


def pg_file_copy(src, dst):
    """src copied to dst the same way; its owner and mode kept."""
    st = os.lstat(src)
    pg_file_put(dst, pg_file_read(src), stat.S_IMODE(st.st_mode), st.st_uid, st.st_gid)


# ---- what a request may hold ---------------------------------------------------------
NAME_RE = re.compile(r'^(?=.{1,253}\Z)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)'
                     r'(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*\Z')
IFACE_RE = re.compile(r'^(?!\.+\Z)[A-Za-z0-9_][A-Za-z0-9_.:-]{0,14}\Z')   # not . or .., not -x (1.0.234)
NODE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,62}\Z')
CERT_RE = re.compile(r'^(\s*-----BEGIN CERTIFICATE-----[A-Za-z0-9+/=\s]+-----END CERTIFICATE-----)+\s*\Z')
KEY_RE = re.compile(r'^\s*-----BEGIN (RSA |EC )?PRIVATE KEY-----[A-Za-z0-9+/=\s:,-]+'
                    r'-----END (RSA |EC )?PRIVATE KEY-----\s*$')
PROTOCOLS = ('TLSv1.2', 'TLSv1.3')
DH_CHOICES = ('none', 'ffdhe2048', 'ffdhe3072', 'ffdhe4096', 'gen2048', 'gen3072', 'gen4096')


def openssl(args, what, data=None):
    got = subprocess.run(['openssl'] + args, capture_output=True, text=True, input=data)
    if got.returncode != 0:
        raise Refused('%s: %s' % (what, (got.stderr or got.stdout).strip().splitlines()[-1:]
                                  or ['openssl said no']))
    return got.stdout


def pem_set(cert, key, chain='', root=''):
    """A certificate, its key, the certificates between it and the root, and
    the root - each read by openssl, the key the certificate's own."""
    cert, key = str(cert or '').strip(), str(key or '').strip()
    chain, root = str(chain or '').strip(), str(root or '').strip()
    if not cert and not key:
        return None
    if not cert or not key:
        raise Refused('a certificate needs its key, and a key its certificate')
    for what, text in (('the certificate', cert), ('the chain', chain), ('the root', root)):
        if text and not CERT_RE.match(text):
            raise Refused('%s is not PEM (-----BEGIN CERTIFICATE-----)' % what)
    if not KEY_RE.match(key):
        raise Refused('the key is not a PEM private key without a passphrase')
    with tempfile.TemporaryDirectory(prefix='otp-web-') as t:
        cf, kf = os.path.join(t, 'c.pem'), os.path.join(t, 'k.pem')
        with open(cf, 'w') as f:
            f.write(cert + '\n')
        with open(kf, 'w') as f:
            f.write(key + '\n')
        os.chmod(kf, 0o600)
        a = openssl(['x509', '-in', cf, '-noout', '-pubkey'], 'the certificate')
        b = openssl(['pkey', '-in', kf, '-pubout'], 'the key')
        if a.strip() != b.strip():
            raise Refused('the key is not the one of this certificate')
    return {'cert': cert + '\n', 'key': key + '\n', 'chain': (chain + '\n') if chain else '',
            'root': (root + '\n') if root else ''}


def tls_checked(t, name):
    if t is None:
        return None
    if not isinstance(t, dict):
        raise Refused('the TLS of %s is not an object' % name)
    out = {'pem': pem_set(t.get('cert'), t.get('key'), t.get('chain'), t.get('root'))}
    alt = t.get('alt')
    if alt and out['pem']:
        # Its second certificate (1.0.196): ECDSA beside RSA, the same names.
        if not isinstance(alt, dict):
            raise Refused('the second certificate of %s is not an object' % name)
        out['pem']['alt'] = pem_set(alt.get('cert'), alt.get('key'), alt.get('chain'), '')
    prot = t.get('protocols') or list(PROTOCOLS)
    if not isinstance(prot, list) or not prot or any(p not in PROTOCOLS for p in prot):
        raise Refused('the protocols are TLSv1.2 and/or TLSv1.3')
    out['protocols'] = [p for p in PROTOCOLS if p in prot]
    ciphers = str(t.get('ciphers') or '').strip()
    if ciphers:
        if not re.match(r'^[A-Za-z0-9_+!@=:.-]{1,2000}\Z', ciphers):
            raise Refused('the ciphers are an OpenSSL cipher list: letters, digits, : + ! - =')
        openssl(['ciphers', ciphers], 'OpenSSL does not know that cipher list')
    out['ciphers'] = ciphers
    out['prefer'] = bool(t.get('prefer'))
    dh = str(t.get('dh') or 'none')
    if dh not in DH_CHOICES:
        raise Refused('the DH parameters are one of %s' % ', '.join(DH_CHOICES))
    out['dh'] = dh
    out['hsts'] = int(t.get('hsts') or 0)
    if not 0 <= out['hsts'] <= 63072000:
        raise Refused('HSTS is 0 to 63072000 seconds')
    return out


def checked(r):
    """The request, every value in the one shape it may have."""
    if not isinstance(r, dict):
        raise Refused('the request is not an object')
    out = {'id': re.sub(r'[^A-Za-z0-9]', '', str(r.get('id') or ''))[:32],
           'hash': re.sub(r'[^0-9a-f]', '', str(r.get('hash') or ''))[:64]}
    node = str(r.get('node') or '')
    if not NODE_RE.match(node):
        raise Refused('the node\'s name is letters, digits, dots, dashes')
    out['node'] = node
    tls = r.get('tls') or {}
    out['tls_node'] = tls_checked(tls.get('node'), 'this node')
    out['tls_vip'] = tls_checked(tls.get('vip'), 'the web address')
    fw = r.get('fw')
    if isinstance(fw, dict):
        rules = fw.get('rules') or []
        # 2000 (1.0.59): a RADIUS rule per client and family came to 400 with
        # 200 clients, and the whole request - certificate, web address and
        # all - was refused for it.
        if not isinstance(rules, list) or len(rules) > 2000:
            raise Refused('the firewall rules are a list, 2000 at most')
        out['fw'] = {'on': bool(fw.get('on')), 'rules': [fw_rule_checked(x) for x in rules]}
    else:
        out['fw'] = None
    out['access'] = access_checked(r.get('access'))
    rp = r.get('realip')
    if rp is None:
        out['realip'] = None                # never asked: nginx's real_ip left alone (1.0.237)
    else:
        nets, head, rec = realip_checked(rp)
        out['realip'] = {'from': nets, 'header': head, 'recursive': rec}
    # The balancer's own address for the enrolment pages (1.0.239): asked only once the sign-in
    # by the balancer was switched on - None leaves nginx as it is.
    sp = r.get('sso_peer')
    out['sso_peer'] = None if sp is None else bool(sp)
    # The balancer's own port (1.0.259): None leaves nginx as it is.
    out['lbport'] = lbport_checked(r.get('lbport'))
    names = r.get('acme')
    if names is None:
        out['acme'] = None
    else:
        if not isinstance(names, list) or len(names) > 10 or \
                not all(isinstance(n, str) and re.match(r'^[A-Za-z0-9][A-Za-z0-9.-]{0,252}\Z', n)
                        for n in names):
            raise Refused('the names of the ACME certificates are DNS names, 10 at most')
        out['acme'] = names
    v = r.get('vip') or {}
    out['vip'] = vip = {'on': bool(v.get('on'))}
    if not vip['on']:
        return out
    try:
        net = plain(v.get('address'), 'interface')
    except ValueError:
        raise Refused('the web address is not an address with its prefix (192.0.2.10/24)')
    if net.ip.is_loopback or net.ip.is_multicast or net.ip.is_unspecified:
        raise Refused('%s cannot be the web address' % net.ip)
    vip['address'], vip['family'] = str(net), net.version
    for k in ('own', 'peer'):
        try:
            a = plain(v.get(k), 'address')
        except ValueError:
            raise Refused('%s is not an address: %r' % (k, str(v.get(k))[:60]))
        if a.version != net.version:
            raise Refused('the nodes\' addresses and the web address are not of one kind '
                          '(IPv4 / IPv6)')
        vip[k] = str(a)
    if vip['own'] == vip['peer'] or str(net.ip) in (vip['own'], vip['peer']):
        raise Refused('the web address must be a third address, not one of the nodes\'')
    iface = str(v.get('iface') or '').strip()
    if iface and not IFACE_RE.match(iface):
        raise Refused('%r is not the name of a network interface' % iface[:20])
    vip['iface'] = iface
    # An IPv6 address of the web address beside the IPv4 one (1.0.119): moved
    # with it by the same VRRP instance; the nodes still speak VRRP over IPv4.
    vip['address6'] = ''
    if v.get('address6'):
        try:
            n6 = plain(v.get('address6'), 'interface')
        except ValueError:
            raise Refused('the IPv6 web address is an address with its prefix (2001:db8::10/64)')
        if n6.version != 6 or n6.ip.is_link_local or n6.ip.is_loopback:
            raise Refused('the IPv6 web address is a global IPv6 address')
        vip['address6'] = str(n6)
    try:
        vip['vrid'] = int(v.get('vrid'))
    except (TypeError, ValueError):
        raise Refused('the VRRP id is a number')
    if not 1 <= vip['vrid'] <= 255:
        raise Refused('the VRRP id is 1 to 255')
    if not re.match(r'^[A-Za-z0-9]{8}\Z', str(v.get('auth') or '')):
        raise Refused('the VRRP password is eight letters and digits')
    vip['auth'] = str(v['auth'])
    fqdn = str(v.get('fqdn') or '').strip().lower().rstrip('.')
    if fqdn and not NAME_RE.match(fqdn):
        raise Refused('%r is not a host name' % fqdn[:80])
    vip['fqdn'] = fqdn
    if out['tls_vip'] and out['tls_vip']['pem'] and not fqdn:
        raise Refused('a certificate of its own needs the name it is for')
    return out


# ---- the parts of the machine it changes ---------------------------------------------
def run(cmd, what, ok=(0,)):
    got = subprocess.run(cmd, capture_output=True, text=True)
    if got.returncode not in ok:
        raise Refused('%s: %s' % (what, (got.stderr or got.stdout).strip()[-300:] or
                                  'ended with %d' % got.returncode))
    return got.stdout


def iface_of(address, near=''):
    """The interface that holds `address` here - or, when none does (the
    node's address just changed, 1.0.120), the one with an address in the
    network of `near` (the web address with its prefix)."""
    out = run(['ip', '-o', 'addr', 'show'], 'ip addr')
    rows = [line.split() for line in out.splitlines()]
    for f in rows:
        if len(f) >= 4 and f[3].split('/')[0] == address:
            return f[1].split('@')[0]
    try:
        net = ipaddress.ip_interface(near).network if near else None
    except ValueError:
        net = None
    if net is not None:
        for f in rows:
            if len(f) < 4 or f[2] not in ('inet', 'inet6') or f[1] == 'lo':
                continue
            try:
                one = ipaddress.ip_interface(f[3])
            except ValueError:
                continue
            if one.ip in net and str(one.ip) != str(ipaddress.ip_interface(near).ip):
                return f[1].split('@')[0]
    raise Refused('no interface here holds %s - is it this node\'s address?' % address)


def keepalived_installed():
    if shutil.which('keepalived'):
        return 'there'
    if NO_SERVICES:
        raise Refused('keepalived is not installed')
    if shutil.which('dnf'):
        run(['dnf', '-y', 'install', 'keepalived'], 'dnf install keepalived')
    elif shutil.which('apt-get'):
        run(['apt-get', 'install', '-y', 'keepalived'], 'apt-get install keepalived')
    else:
        raise Refused('install keepalived on this machine, then turn the address on again')
    return 'installed now'


def ka_ours():
    try:
        with open(KA_CONF) as f:
            head = f.read(len(MARK) + 10)
    except FileNotFoundError:
        return None                                     # nobody's
    return head.startswith(MARK)


def ka_conf(node, v):
    lines = [
        MARK,
        '# The web address of the cluster: %s on one node at a time.' % v['address'],
        '# RADIUS does not use it - both nodes answer RADIUS on their own addresses.',
        'global_defs {',
        '    router_id otp_%s' % re.sub(r'[^A-Za-z0-9_]', '_', node),
        '    enable_script_security',
        '    script_user otp',
        '    vrrp_garp_master_refresh 60',
        '}',
        '',
        '# May this node hold it? otp answering, not in maintenance, not being upgraded.',
        'vrrp_script otp_ok {',
        '    script "%s ok"' % CHECK,
        '    interval 2',
        '    timeout 3',
        '    fall 2',
        '    rise 2',
        '}',
        '',
        '# Is it the node the address is meant to be on? (moved on the pages)',
        'vrrp_script otp_prefer {',
        '    script "%s prefer"' % CHECK,
        '    interval 2',
        '    timeout 3',
        '    weight 50',
        '    fall 1',
        '    rise 1',
        '}',
        '',
        'vrrp_instance otp_web {',
        '    state BACKUP',
        '    interface %s' % v['iface'],
        '    virtual_router_id %d' % v['vrid'],
        '    priority 100',
        '    advert_int 1',
        '    preempt_delay 5',
        '    unicast_src_ip %s' % v['own'],
        '    unicast_peer {',
        '        %s' % v['peer'],
        '    }',
    ]
    if v['family'] == 4:
        lines += ['    authentication {', '        auth_type PASS',
                  '        auth_pass %s' % v['auth'], '    }']
    lines += [
        '    virtual_ipaddress {',
        '        %s dev %s' % (v['address'], v['iface']),
        '    }',
    ]
    if v.get('address6'):
        # Of the other family than the VRRP packets: excluded from them,
        # moved with the instance all the same.
        lines += ['    virtual_ipaddress_excluded {',
                  '        %s dev %s' % (v['address6'], v['iface']),
                  '    }']
    lines += [
        '    track_script {',
        '        otp_ok',
        '        otp_prefer',
        '    }',
        '    notify "%s notify"' % CHECK,
        '}',
        '',
    ]
    return '\n'.join(lines)


def firewall(peer, family, on):
    if NO_SERVICES or not shutil.which('firewall-cmd'):
        return ''
    if subprocess.run(['firewall-cmd', '--state'], capture_output=True).returncode != 0:
        return 'firewalld is not running: let VRRP (IP protocol 112) from %s in yourself' % peer
    rule = 'rule family="%s" source address="%s" protocol value="vrrp" accept' % (
        'ipv6' if family == 6 else 'ipv4', peer)
    got = subprocess.run(['firewall-cmd', '--permanent',
                          ('--add-rich-rule=' if on else '--remove-rich-rule=') + rule],
                         capture_output=True, text=True)
    rl = subprocess.run(['firewall-cmd', '--reload'], capture_output=True, text=True)
    # Said when it did not work (1.0.57): VRRP not let in is both nodes
    # holding the address.
    if on and (got.returncode not in (0,) and 'ALREADY_ENABLED' not in (got.stderr or '')
               or rl.returncode != 0):
        return 'firewalld did NOT let VRRP from %s in: %s' % (
            peer, ((got.stderr or rl.stderr or '').strip().splitlines() or ['?'])[-1][:200])
    return 'firewalld: VRRP from %s %s' % (peer, 'let in' if on else 'no longer let in')


REALIP_BEGIN = '    # OTP-REALIP-BEGIN - behind a load balancer or WAF, as set on the pages\n'
REALIP_END = '    # OTP-REALIP-END\n'
HEADER_RE = re.compile(r'^[A-Za-z][A-Za-z0-9-]{0,63}\Z')


def realip_checked(rp):
    """The balancers and the header as the daemon asked - checked again here: they go into
    nginx's configuration as they are."""
    if not isinstance(rp, dict):
        raise Refused('realip: not an object')
    nets = []
    for w in (rp.get('from') or [])[:64]:
        try:
            nets.append(str(plain(w, 'network')))    # no scope id: a line of its own (1.0.248)
        except ValueError:
            raise Refused('realip: %r is not an address or a network' % str(w)[:60])
    head = str(rp.get('header') or 'X-Forwarded-For')
    if nets and (not HEADER_RE.match(head) or head.lower() in ('host', 'cookie', 'authorization')):
        raise Refused('realip: %r is not the name of a header' % head[:60])
    return nets, head, bool(rp.get('recursive'))


def lbport_checked(lp):
    """The balancer's own port as the daemon asked (1.0.259): {'port': 0} takes it away."""
    if lp is None:
        return None
    if not isinstance(lp, dict):
        raise Refused('lbport: not an object')
    try:
        port = int(lp.get('port') or 0)
    except (TypeError, ValueError):
        raise Refused('lbport: the port is not a number')
    if not port:
        return {'port': 0}
    if not 1024 <= port <= 65535:
        raise Refused('lbport: the port is from 1024 to 65535')
    head = str(lp.get('header') or 'X-Forwarded-For')
    if head == 'proxy_protocol':
        nets, _h, _r = realip_checked({'from': lp.get('from'), 'header': 'X-Forwarded-For'})
        rec = False
    else:
        nets, head, rec = realip_checked({'from': lp.get('from'), 'header': head,
                                          'recursive': lp.get('recursive')})
    if not nets:
        raise Refused('lbport: the balancers\' addresses are not given')
    return {'port': port, 'from': nets, 'header': head, 'recursive': rec}


LB_HEAD = ('# otp: the load balancer\'s own port (1.0.259) - the enrolment pages only, never the\n'
           '# administration, /metrics or /healthz. Made from the HTTPS server of otp.conf again\n'
           '# whenever either is changed on the pages: not to be edited (Settings - Firewall and access).\n')
# What the balancer's server takes over from the HTTPS server of otp.conf: its TLS, its headers,
# where it logs - one line each, at the server's own level.
LB_KEEP = ('ssl_', 'add_header', 'root', 'index', 'server_tokens', 'gzip', 'access_log',
           'error_log', 'client_body_timeout', 'http2')
LB_ASSETS = r'^/assets/(core\.js|portal\.js|i18n\.js|otp\.css|favicon\.svg|apple-touch-icon\.png)$'


def block_at(text, start):
    """The text of the { } block whose opening brace is the first one from `start`."""
    i = text.index('{', start)
    depth = 0
    for j in range(i, len(text)):
        if text[j] == '{':
            depth += 1
        elif text[j] == '}':
            depth -= 1
            if depth == 0:
                return text[start:j + 1]
    raise Refused('a block of %s does not end' % NGINX_MAIN)


def lbport_server(main, lp):
    """The server { } of the balancer's own port: the TLS and headers of this node's HTTPS
    server, its enrolment page as it is there (who may reach it, the limits, the balancer that
    signs people in), the files that page needs - and nothing else."""
    where = server_block(main)
    if not where:
        raise Refused('no HTTPS server { } was found in %s' % NGINX_MAIN)
    block = main[where[0]:where[1]]
    body = block[block.index('{') + 1:block.rindex('}')]
    keep, depth = [], 0
    for line in body.split('\n'):
        k = line.strip()
        if depth == 0 and k.endswith(';') and '{' not in k and k.split(None, 1)[0].startswith(LB_KEEP):
            keep.append('    ' + k)
        depth += line.count('{') - line.count('}')
    m = re.search(r'(?m)^[ \t]*location[ \t]*=[ \t]*/[ \t]*\{', block)
    if not m:
        raise Refused('no location = / { } (the enrolment pages) in the HTTPS server of %s' % NGINX_MAIN)
    portal = block_at(block, m.start())
    portal = re.sub(r'(?m)^[ \t]*', '', portal)
    lines = portal.split('\n')
    portal = '\n'.join(['    ' + lines[0]] + ['        ' + x for x in lines[1:-1]] + ['    ' + lines[-1]])
    lm = re.search(r'(?m)^\s*listen\s+(?:[0-9.]+:)?443\b([^;]*);', body)
    # TLS and HTTP/2 as on 443 (the old spelling of http2 where nginx is older than 1.25.1).
    opts = ['ssl'] + (['http2'] if lm and 'http2' in lm.group(1).split() else [])
    pp = lp['header'] == 'proxy_protocol'
    if pp:
        opts.append('proxy_protocol')
    port = int(lp['port'])
    out = ['server {', '    listen %d %s;' % (port, ' '.join(opts))]
    if re.search(r'(?m)^\s*listen\s+\[::\]:443\b', body):
        out.append('    listen [::]:%d %s;' % (port, ' '.join(opts)))
    out.append('    server_name _;')
    out += keep
    out.append('    # the balancers alone are believed - %s' % (
        'the client\'s address in the PROXY protocol' if pp else 'the client\'s address in ' + lp['header']))
    out += ['    set_real_ip_from %s;' % n for n in lp['from']]
    out.append('    real_ip_header %s;' % lp['header'])
    out.append('    real_ip_recursive %s;' % ('on' if lp.get('recursive') else 'off'))
    out += ['    client_max_body_size 8m;',
            '    if ($request_method !~ ^(GET|HEAD|POST)$) { return 405; }',
            '    if ($http_content_type ~* "multipart") { return 403; }',
            portal,
            '    location = /index.php { return 301 /; }',
            '    location ~ %s {' % LB_ASSETS,
            '        expires 7d;', '        access_log off;', '        try_files $uri =404;', '    }',
            '    location = /favicon.ico { return 301 /assets/favicon.svg; }',
            '    location ~ ^/apple-touch-icon(-precomposed)?(-[0-9]+x[0-9]+)?\\.png$ {',
            '        rewrite ^ /assets/apple-touch-icon.png last;', '    }',
            '    # nothing else: the administration, /metrics, /healthz and every other path',
            '    location / { return 404; }', '}']
    return '\n'.join(out) + '\n'


def realip_into(main, rp):
    """otp's own real_ip lines in the HTTPS server of this node (the VIP address's server is made
    from it): put in, changed or taken out. On, they take the place of what otp --trusted-proxy
    wrote; off, only otp's own go - nothing else of nginx is touched (1.0.237)."""
    nets, head, rec = realip_checked(rp)
    where = server_block(main)
    if not where:
        raise Refused('no HTTPS server { } was found in %s' % NGINX_MAIN)
    block = main[where[0]:where[1]]
    new = re.sub(r'    # OTP-REALIP-BEGIN.*?# OTP-REALIP-END\n', '', block, flags=re.S)
    if nets:
        new = re.sub(r'    # REALIP-BEGIN.*?# REALIP-END\n', '', new, flags=re.S)
        lines = (REALIP_BEGIN + ''.join('    set_real_ip_from %s;\n' % n for n in nets) +
                 '    real_ip_header %s;\n' % head +
                 '    real_ip_recursive %s;\n' % ('on' if rec else 'off') + REALIP_END)
        head_end = new.index('{') + 1
        nl = new.find('\n', head_end)
        cut = nl + 1 if nl >= 0 else head_end
        new = new[:cut] + lines + new[cut:]
    return main[:where[0]] + new + main[where[1]:]


SSO_PEER_MARK = '# OTP-SSO-PEER'


def sso_peer_into(main, on):
    """The address of the machine the request really came from - the balancer's, not the client's
    from X-Forwarded-For - passed to the enrolment page as OTP_PEER, so that only the balancers
    named can sign people in (1.0.239). In `location = /` of this node's HTTPS server (the VIP
    address's server is made from it); off, only that line goes."""
    where = server_block(main)
    if not where:
        raise Refused('no HTTPS server { } was found in %s' % NGINX_MAIN)
    block = main[where[0]:where[1]]
    new = re.sub(r'(?m)^[ \t]*fastcgi_param[ \t]+OTP_PEER[^\n]*%s[^\n]*\n' % re.escape(SSO_PEER_MARK),
                 '', block)
    if on:
        m = re.search(r'(?m)^([ \t]*)location[ \t]*=[ \t]*/[ \t]*\{[^\n]*\n', new)
        if not m:
            raise Refused('no location = / { } (the enrolment pages) in the HTTPS server of %s'
                          % NGINX_MAIN)
        pad = m.group(1) + '    '
        new = new[:m.end()] + ('%sfastcgi_param  OTP_PEER $realip_remote_addr;   %s - the '
                               'balancer that signs people in\n' % (pad, SSO_PEER_MARK)) + \
            new[m.end():]
    return main[:where[0]] + new + main[where[1]:]


def server_block(text):
    """(start, end) of the HTTPS server { } of an nginx file."""
    i = 0
    while True:
        m = re.search(r'(?m)^[ \t]*server[ \t]*\{', text[i:])
        if not m:
            return None
        start = i + m.start()
        depth, j = 0, i + m.end() - 1
        while j < len(text):
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        block = text[start:j + 1]
        if re.search(r'(?m)^\s*listen\s+[^;]*443[^;]*ssl', block) or \
                re.search(r'(?m)^\s*ssl_certificate\s', block):
            return start, j + 1
        i = j + 1


def set_directive(block, name, value):
    """`name value;` in a server { } - replaced where it is, put in after
    server_name where it is not, taken out for None. Only the server's own
    lines: a location { } inside is left alone."""
    lines = block.split('\n')
    depth, at, insert_at = 0, [], None
    for n, line in enumerate(lines):
        if depth == 1 and re.match(r'^\s*%s\s' % re.escape(name), line):
            at.append(n)
        if depth == 1 and insert_at is None and re.match(r'^\s*server_name\s', line):
            insert_at = n + 1
        depth += line.count('{') - line.count('}')
    if value is None:
        for n in reversed(at):
            del lines[n]
        return '\n'.join(lines)
    # Several of one name (1.0.196: two certificates, RSA and ECDSA) - a list.
    values = value if isinstance(value, (list, tuple)) else [value]
    texts = ['    %-25s %s;' % (name, v) for v in values]
    if at:
        for n in reversed(at[1:]):
            del lines[n]
        lines[at[0]:at[0] + 1] = texts
    else:
        pos = insert_at if insert_at is not None else 1
        lines[pos:pos] = texts
    return '\n'.join(lines)


CIPHERS_DEFAULT = ('ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:'
                   'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:'
                   'ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305')


# How it is going, for the pages (1.0.50): the step, how many there are,
# what is being done, and - for the long one, making DH parameters - when it
# began and about how long it takes.
PROGRESS = {'step': 0, 'total': 6, 'id': ''}
DH_READY = {}
DH_EXPECT_S = {'gen2048': 15, 'gen3072': 120, 'gen4096': 600}


def progress(words, step=None, expect=None):
    if step is not None:
        PROGRESS['step'] = step
    try:
        write_here('progress.json', json.dumps({
            'id': PROGRESS['id'], 'step': PROGRESS['step'], 'total': PROGRESS['total'],
            'words': words, 'at': time.time(), 'expect_s': expect}))
    except OSError:
        pass


def dh_file(choice, path, had):
    """The DH parameters for `choice` in `path`: a group of RFC 7919, or made
    here (which takes a while - 4096 bits minutes). Made ones are made once."""
    if choice == 'none':
        return None
    if choice == had and os.path.exists(path):
        return path
    if choice.startswith('ffdhe'):
        pem = openssl(['genpkey', '-genparam', '-algorithm', 'DH', '-pkeyopt',
                       'group:%s' % choice], 'the DH group %s' % choice)
    else:
        progress('making DH parameters of %s bits' % choice[3:], 2, DH_EXPECT_S.get(choice))
        pem = openssl(['dhparam', choice[3:]], 'making DH parameters of %s bits' % choice[3:])
    write_root(path, pem, 0o644)
    return path


TLS_FILES_NEW = [False]           # a certificate or key file of nginx's changed (1.0.205)


def _tls_put(path, text, mode):
    """A certificate or key file written; noted when it is not what was there."""
    try:
        with open(path, 'rb') as f:
            same = f.read() == text.encode('utf-8')
    except OSError:
        same = False
    write_root(path, text, mode)
    if not same:
        TLS_FILES_NEW[0] = True


def tls_into(block, t, files, had_dh):
    """A server { } with the TLS of `t`: its files written, its lines set.
    Returns (block, words, dh made)."""
    said = []
    progress('writing the certificate and the TLS settings', 3)
    if t['pem']:
        full = t['pem']['cert'] + t['pem']['chain']
        _tls_put(files['cert'], full, 0o644)
        _tls_put(files['key'], t['pem']['key'], 0o600)
        alt = t['pem'].get('alt')
        if alt:
            # RSA first, the default; ECDSA to the clients that take it (1.0.196).
            _tls_put(files['cert2'], alt['cert'] + alt['chain'], 0o644)
            _tls_put(files['key2'], alt['key'], 0o600)
            block = set_directive(block, 'ssl_certificate', [files['cert'], files['cert2']])
            block = set_directive(block, 'ssl_certificate_key', [files['key'], files['key2']])
        else:
            block = set_directive(block, 'ssl_certificate', files['cert'])
            block = set_directive(block, 'ssl_certificate_key', files['key'])
        if t['pem']['root']:
            _tls_put(files['root'], t['pem']['root'] + t['pem']['chain'], 0o644)
            block = set_directive(block, 'ssl_trusted_certificate', files['root'])
        else:
            block = set_directive(block, 'ssl_trusted_certificate', None)
        subj = openssl(['x509', '-noout', '-subject', '-enddate'], 'the certificate',
                       t['pem']['cert']).strip().replace('\n', ', ')
        said.append('certificate: %s' % subj)
    block = set_directive(block, 'ssl_protocols', ' '.join(t['protocols']))
    block = set_directive(block, 'ssl_ciphers', t['ciphers'] or CIPHERS_DEFAULT)
    block = set_directive(block, 'ssl_prefer_server_ciphers', 'on' if t['prefer'] else 'off')
    dh = DH_READY.get(files['dh'], 'none?')
    if dh == 'none?':
        dh = dh_file(t['dh'], files['dh'], had_dh)
    block = set_directive(block, 'ssl_dhparam', dh)
    if t['hsts']:
        block = set_directive(block, 'add_header Strict-Transport-Security',
                              '"max-age=%d" always' % t['hsts'])
    else:
        block = set_directive(block, 'add_header Strict-Transport-Security', None)
    said.append('%s; %s; DH %s%s' % (' '.join(t['protocols']),
                                     'ciphers as set' if t['ciphers'] else 'the usual ciphers',
                                     t['dh'], '; HSTS %d s' % t['hsts'] if t['hsts'] else ''))
    return block, said, t['dh']


NODE_FILES = {'cert': os.path.join(CERT_DIR, 'otp.pem'), 'key': os.path.join(CERT_DIR, 'otp.key'),
              'cert2': os.path.join(CERT_DIR, 'otp-ecdsa.pem'), 'key2': os.path.join(CERT_DIR, 'otp-ecdsa.key'),
              'root': os.path.join(CERT_DIR, 'otp-ca.pem'),
              'dh': os.path.join(CERT_DIR, 'otp-dh.pem')}
VIP_FILES = {'cert': os.path.join(CERT_DIR, 'otp-vip.pem'),
             'key': os.path.join(CERT_DIR, 'otp-vip.key'),
             'cert2': os.path.join(CERT_DIR, 'otp-vip-ecdsa.pem'),
             'key2': os.path.join(CERT_DIR, 'otp-vip-ecdsa.key'),
             'root': os.path.join(CERT_DIR, 'otp-vip-ca.pem'),
             'dh': os.path.join(CERT_DIR, 'otp-vip-dh.pem')}


def snapshot(paths):
    got = {}
    for p in paths:
        try:
            with open(p, 'rb') as f:
                got[p] = (f.read(), os.stat(p).st_mode & 0o777)
        except FileNotFoundError:
            got[p] = None
    return got


def put_back(snap):
    for p, was in snap.items():
        if was is None:
            try:
                os.unlink(p)
            except OSError:
                pass
        else:
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p))
            with os.fdopen(fd, 'wb') as f:
                f.write(was[0])
                f.flush()
                os.fchmod(f.fileno(), was[1])     # the file itself (1.0.205)
            os.replace(tmp, p)
            # Its SELinux label too, not the folder's (1.0.57).
            if shutil.which('restorecon'):
                subprocess.run(['restorecon', p], capture_output=True)


SYSCTL_FILE = '/etc/sysctl.d/90-otp-vip.conf'


def nonlocal_bind(family, also=None):
    """nginx may listen on the web address on the node that does not hold
    it - so it answers at once when the address comes over."""
    keys = []
    for fam in (family, also):
        if fam:
            k = 'net.ipv6.ip_nonlocal_bind' if fam == 6 else 'net.ipv4.ip_nonlocal_bind'
            if k not in keys:
                keys.append(k)
    want = '%s\n%s\n' % (MARK, '\n'.join('%s = 1' % k for k in keys))
    try:
        with open(SYSCTL_FILE) as f:
            if f.read() == want:
                return ''
    except OSError:
        pass
    if NO_SERVICES:
        return ''
    write_root(SYSCTL_FILE, want, 0o644)
    for k in keys:
        subprocess.run(['sysctl', '-w', '%s=1' % k], capture_output=True)
    return 'sysctl: %s = 1 (nginx listens on the web address on both nodes)' % ', '.join(keys)


# ---- who may reach which pages (1.0.52) -----------------------------------------------
# otp.conf has a list of its own for the enrolment pages, the administration
# pages and /healthz, between marks (install.sh writes the first two). The
# pages set them; the cluster's own addresses are always among them.
ACCESS_PAGES = (('portal', 'PORTAL', 'location = / {'), ('admin', 'ADMIN', 'location = /admin/ {'),
                ('health', 'HEALTH', 'location = /healthz {'))


def access_checked(a):
    if not isinstance(a, dict):
        return None
    out = {}
    for k, _m, _l in ACCESS_PAGES:
        one = a.get(k)
        if not isinstance(one, dict):
            raise Refused('who may reach the %s pages is not given' % k)
        nets = []
        for x in (one.get('from') or [])[:400]:     # the cluster's on top of 200 (1.0.59)
            try:
                nets.append(str(plain(x, 'network')))
            except ValueError:
                raise Refused('%r is not an address or a network' % str(x)[:60])
        if not one.get('any') and not nets:
            raise Refused('the %s pages would be for nobody: give a network or everybody' % k)
        out[k] = {'any': bool(one.get('any')), 'from': list(dict.fromkeys(nets))}
    return out


def access_lines(one, pad):
    if one['any']:
        return pad + 'allow all;                    # everybody (Settings - Firewall)'
    return '\n'.join('%sallow %s;' % (pad, n) for n in one['from'])


def access_into(text, access):
    """otp.conf with the three lists as asked."""
    for k, mark, loc in ACCESS_PAGES:
        rx = re.compile(r'([ \t]*)# %s-ALLOW-BEGIN\n(?:.*?\n)?([ \t]*)# %s-ALLOW-END' % (mark, mark),
                        re.S)
        if not rx.search(text):
            # Not there yet (the /healthz one, or a file from before): put in,
            # with the only other two lines a list needs, in every HTTPS server
            # that has this location.
            i = 0
            while True:
                i = text.find(loc, i)
                if i < 0:
                    break
                j = text.index('\n', i) + 1
                pad = re.match(r'[ \t]*', text[text.rfind('\n', 0, i) + 1:]).group(0) + '    '
                text = (text[:j] + '%s# %s-ALLOW-BEGIN\n%s# %s-ALLOW-END\n%sallow 127.0.0.1;\n'
                        '%sallow ::1;\n%sdeny  all;\n' % (pad, mark, pad, mark, pad, pad, pad) +
                        text[j:])
                i = j
        text = rx.sub(lambda m: '%s# %s-ALLOW-BEGIN\n%s\n%s# %s-ALLOW-END' % (
            m.group(1), mark, access_lines(access[k], m.group(1)), m.group(2), mark), text)
    return text


def access_now():
    """What otp.conf says now, for the pages."""
    try:
        with open(NGINX_MAIN) as f:
            text = f.read()
    except OSError:
        return {}
    out = {}
    for k, mark, _l in ACCESS_PAGES:
        m = re.search(r'# %s-ALLOW-BEGIN\n(.*?)\n[ \t]*# %s-ALLOW-END' % (mark, mark), text, re.S)
        if not m:
            out[k] = {'any': True, 'from': [], 'marked': False}
            continue
        nets = re.findall(r'(?m)^\s*allow\s+([^;\s]+);', m.group(1))
        out[k] = {'any': 'all' in nets, 'from': [n for n in nets if n != 'all'], 'marked': True}
    return out


ACME_LOCATION = '''    # A certificate by ACME (1.0.169): the CA's HTTP-01 challenge answered on
    # port 80 by acme.php - the answer is in otp's database, so whichever node
    # the CA reaches gives it. Everything else goes to HTTPS.
    location ^~ /.well-known/acme-challenge/ {
        limit_req     zone=otp_all burst=20 nodelay;
        if ($http_content_type ~* "multipart") { return 403; }
        fastcgi_pass  unix:/run/php-fpm/otp.sock;
        fastcgi_param SCRIPT_FILENAME /var/www/otp/acme.php;
        include       fastcgi_params;
        fastcgi_read_timeout 10s;
    }
    location / {
        return 301 https://$host$request_uri;
    }'''


def http_block(text):
    """(start, end) of the port-80 server { } of an nginx file."""
    for m in re.finditer(r'(?m)^[ \t]*server[ \t]*\{', text):
        depth, j = 0, m.end() - 1
        while j < len(text):
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        block = text[m.start():j + 1]
        if re.search(r'(?m)^\s*listen\s+(\[::\]:)?80\b', block) and 'ssl' not in block.split('{', 1)[1][:400]:
            return m.start(), j + 1
    return None


def acme_into(main, names):
    """The port-80 server given the ACME location (1.0.169), and the names
    certificates are ordered for in its server_name - the web address's on
    every node, so the CA reaches otp on whichever node has it."""
    where = http_block(main)
    if not where:
        return main
    block = main[where[0]:where[1]]
    new = block
    if 'acme-challenge' not in new:
        # The pool's socket as the file's own server blocks have it (1.0.252): Debian's is
        # /run/php/otp.sock, and the location put in answered 502 there.
        sock = re.search(r'(?m)^\s*fastcgi_pass\s+(unix:[^;\s]+);', main)
        loc = ACME_LOCATION.replace('unix:/run/php-fpm/otp.sock', sock.group(1)) if sock else ACME_LOCATION
        new = re.sub(r'(?m)^[ \t]*return[ \t]+301[ \t]+https://\$host\$request_uri;[ \t]*$',
                     lambda m: loc, new, count=1)
    m = re.search(r'(?m)^(\s*server_name\s+)([^;#]*);', new)
    if m and names:
        have = m.group(2).split()
        base = [x for x in have if not x.startswith('otp-acme:')]
        want = base + [n for n in names if n not in base]
        if want != have:
            new = new[:m.start()] + m.group(1) + ' '.join(want) + ';' + new[m.end():]
    return main[:where[0]] + new + main[where[1]:] if new != block else main


def lbport_selinux(port):
    """The balancer's own port let to nginx where SELinux is on (1.0.262), or Refused on an
    enforcing node where it cannot be: written without it, nginx could not bind it - reloaded,
    the port stayed shut; restarted (an upgrade), nginx did not start at all. A port http_port_t
    or http_cache_port_t has already is left as it is."""
    mode = se_mode()
    if mode in ('absent', 'Disabled'):
        return ''
    enforcing = mode == 'Enforcing'
    known = se_ports()
    if known is None:
        if enforcing:
            raise Refused('SELinux is enforcing and semanage is not on this machine, so nginx '
                          'cannot be let listen on the balancer\'s port %d (dnf install '
                          'policycoreutils-python-utils)' % port)
        return ''
    if se_port_has(known, 'http_port_t', 'tcp', port) or \
            se_port_has(known, 'http_cache_port_t', 'tcp', port):
        return ''
    got = _se_run(['semanage', 'port', '-a', '-t', 'http_port_t', '-p', 'tcp', str(port)], 300)
    if got is not None and got.returncode == 0:
        return 'SELinux lets nginx listen on the balancer\'s port %d' % port
    if got is not None and 'already defined' in (got.stderr or ''):
        why = ('port %d/tcp is another service\'s in the SELinux policy - choose another port for '
               'the balancer (web_proxy_port)' % port)
    else:
        why = 'semanage port %d/tcp: %s' % (port, ((got.stderr or '') if got else '').strip()[-200:])
    if enforcing:
        raise Refused(why)
    return 'SELinux (permissive): %s' % why


def lbport_listening(port, wait=5.0):
    """nginx answers on the balancer's own port (a TCP connect to 127.0.0.1 - it listens on
    every address), `wait` seconds at most."""
    import socket
    end = time.time() + wait
    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            if s.connect_ex(('127.0.0.1', int(port))) == 0:
                return True
        except OSError:
            pass
        finally:
            s.close()
        if time.time() >= end:
            return False
        time.sleep(0.25)


def nginx_part(r, last):
    """This node's server and the web address's, with their TLS."""
    said, dh = [], {}
    # DH parameters made first (1.0.50): it can take minutes, and nginx's file
    # is read only after it, so nothing changed in it meanwhile (an upgrade)
    # is written over with an older copy.
    for t, files, which in ((r['tls_node'], NODE_FILES, 'node'),
                            (r['tls_vip'] if r['vip']['on'] else None, VIP_FILES, 'vip')):
        if not t:
            continue
        # The same parameters made for the node serve the web address too
        # (1.0.51): made once, not twice.
        if which == 'vip' and t['dh'].startswith('gen') and r['tls_node'] and \
                r['tls_node']['dh'] == t['dh'] and DH_READY.get(NODE_FILES['dh']) and \
                (last.get('dh') or {}).get('vip') != t['dh']:
            shutil.copyfile(NODE_FILES['dh'], files['dh'])
            os.chmod(files['dh'], 0o644)
            DH_READY[files['dh']] = files['dh']
            continue
        DH_READY[files['dh']] = dh_file(t['dh'], files['dh'], (last.get('dh') or {}).get(which))
    paths = [NGINX_MAIN, NGINX_VIP, NGINX_LB] + list(NODE_FILES.values()) + list(VIP_FILES.values())
    snap = snapshot(paths)
    changed = False
    TLS_FILES_NEW[0] = False
    try:
        try:
            with open(NGINX_MAIN) as f:
                main = f.read()
        except OSError as e:
            raise Refused('otp\'s nginx file cannot be read (%s): %s' % (NGINX_MAIN, e))
        if r.get('acme') is not None:
            new_main = acme_into(main, r['acme'])
            if new_main != main:
                write_root(NGINX_MAIN, new_main, 0o644)
                main, changed = new_main, True
                said.append('nginx: port 80 answers the ACME CA (%s)' % (', '.join(r['acme']) or
                                                                        'no name yet'))
        if r.get('access'):
            new_main = access_into(main, r['access'])
            if new_main != main:
                write_root(NGINX_MAIN, new_main, 0o644)
                main, changed = new_main, True
                said.append('nginx: who may reach the enrolment, administration and health '
                            'pages set')
        if r.get('realip') is not None:
            new_main = realip_into(main, r['realip'])
            if new_main != main:
                write_root(NGINX_MAIN, new_main, 0o644)
                main, changed = new_main, True
                rp = r['realip']
                said.append('nginx: the client\'s address from %s when it comes from %s'
                            % (rp.get('header'), ', '.join(rp.get('from')))
                            if rp.get('from') else 'nginx: no balancer believed any more')
        if r.get('sso_peer') is not None:
            new_main = sso_peer_into(main, r['sso_peer'])
            if new_main != main:
                write_root(NGINX_MAIN, new_main, 0o644)
                main, changed = new_main, True
                said.append('nginx: the enrolment pages told which machine a request came from '
                            '(signed in by the load balancer)' if r['sso_peer'] else
                            'nginx: the enrolment pages no longer told which machine a request '
                            'came from')
        where = server_block(main)
        if not where:
            raise Refused('no HTTPS server { } was found in %s' % NGINX_MAIN)
        block = main[where[0]:where[1]]
        if r['tls_node']:
            new, words, dh['node'] = tls_into(block, r['tls_node'], NODE_FILES,
                                              (last.get('dh') or {}).get('node'))
            if new != block:
                write_root(NGINX_MAIN, main[:where[0]] + new + main[where[1]:], 0o644)
                changed = True
            said += ['this node: ' + w for w in words]
            block = new
        vip, tv = r['vip'], r['tls_vip']
        if vip['on'] and tv and tv['pem']:
            vb = re.sub(r'(?m)^(\s*)server_name\s+[^;]*;', r'\1server_name %s;' % vip['fqdn'],
                        block, count=1)
            vb = re.sub(r'\s+default_server\b', '', vb)
            # Its own address as well as its name (1.0.51): a browser that
            # asks for the address itself, or sends no name at all, gets the
            # web address's certificate - not the node's. The address need
            # not be on this node for nginx to listen on it (ip_nonlocal_bind).
            ip = vip['address'].split('/')[0]
            host = '[%s]' % ip if ':' in ip else ip
            vb = re.sub(r'(?m)^(\s*)listen\s+(?:\[[^\]]*\]:|[0-9.]+:)?443\b([^;]*);',
                        r'\1listen %s:443\2;' % host, vb)
            lines, seen = [], set()
            for line in vb.split('\n'):
                k = line.strip()
                if k.startswith('listen ') and k in seen:
                    continue
                seen.add(k)
                lines.append(line)
            vb = '\n'.join(lines)
            if vip.get('address6'):
                ip6 = vip['address6'].split('/')[0]
                vb = re.sub(r'(?m)^(\s*)(listen\s+%s:443\b[^;]*;)' % re.escape(host),
                            lambda m: '%s%s\n%slisten [%s]:443%s;' % (
                                m.group(1), m.group(2), m.group(1), ip6,
                                m.group(2).split(':443', 1)[1].rstrip(';')), vb, count=1)
            said.append(nonlocal_bind(vip['family'], 6 if vip.get('address6') else None))
            vb, words, dh['vip'] = tls_into(vb, tv, VIP_FILES, (last.get('dh') or {}).get('vip'))
            text = ('%s\n# %s - the web address\'s own name and certificate: a copy of the '
                    'HTTPS server of otp.conf,\n# made again whenever either is changed on the '
                    'pages.\n%s\n' % (MARK, vip['fqdn'], vb))
            if snap.get(NGINX_VIP) is None or snap[NGINX_VIP][0].decode() != text:
                write_root(NGINX_VIP, text, 0o644)
                changed = True
            said += ['the web address (%s): ' % vip['fqdn'] + w for w in words]
        elif os.path.exists(NGINX_VIP):
            os.unlink(NGINX_VIP)
            try:
                os.unlink(SYSCTL_FILE)
            except OSError:
                pass
            for p in VIP_FILES.values():
                try:
                    os.unlink(p)
                except OSError:
                    pass
            changed = True
            said.append('nginx: the web address\'s own server taken away (it answers with this '
                        'node\'s certificate)')
        # The balancer's own port (1.0.259): made from this node's server as it is now.
        lp = r.get('lbport')
        lb_look = 0
        if lp is not None and lp.get('port'):
            text = LB_HEAD + lbport_server(main[:where[0]] + block + main[where[1]:], lp)
            if snap.get(NGINX_LB) is None or snap[NGINX_LB][0].decode() != text:
                # Let to nginx by SELinux first (1.0.262), or refused before anything is written.
                w = lbport_selinux(int(lp['port']))
                if w:
                    said.append(w)
                write_root(NGINX_LB, text, 0o644)
                changed = True
                lb_look = int(lp['port'])
                said.append('nginx: the balancer\'s own port %d - the enrolment pages only, for %s%s'
                            % (lp['port'], ', '.join(lp['from']),
                               ' (the PROXY protocol)' if lp['header'] == 'proxy_protocol' else ''))
            elif not NO_SERVICES and not lbport_listening(int(lp['port']), 0):
                # Written by 1.0.259-1.0.261 without its label: nginx never listened there.
                w = lbport_selinux(int(lp['port']))
                if w:
                    said.append(w)
                    changed = True
                    lb_look = int(lp['port'])
        elif lp is not None and os.path.exists(NGINX_LB):
            os.unlink(NGINX_LB)
            changed = True
            said.append('nginx: the balancer\'s own port taken away')
        # A certificate renewed changes no line of nginx's (1.0.205): its files
        # alone were written, nginx was not reloaded, and went on giving the
        # old one until it ran out.
        if TLS_FILES_NEW[0]:
            changed = True
        if changed and not NO_SERVICES:
            progress('asking nginx, and reloading it', 4)
            t = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
            if t.returncode != 0:
                raise Refused('nginx does not take it, so it is as it was: %s'
                              % ((t.stderr or '').strip().splitlines() or ['?'])[-1][:300])
            rl = subprocess.run(['systemctl', 'reload', 'nginx'], capture_output=True, text=True)
            if rl.returncode != 0:
                # nginx not run by systemd here (started by hand, a container): its own signal
                rl2 = subprocess.run(['nginx', '-s', 'reload'], capture_output=True, text=True)
                if rl2.returncode == 0:
                    rl = rl2
            if rl.returncode != 0:
                # Said, not "reloaded" (1.0.262): the files put back (nginx runs what it ran).
                raise Refused('nginx could not be reloaded, so it is as it was: %s'
                              % (((rl.stderr or '').strip().splitlines() or ['?'])[-1][:300]))
            said.append('nginx reloaded')
            if lb_look and not lbport_listening(lb_look):
                # nginx not run by systemd (a systemctl that answers without reloading it): its
                # own signal, and a look again
                subprocess.run(['nginx', '-s', 'reload'], capture_output=True)
            if lb_look and not lbport_listening(lb_look):
                # Reloaded, and the balancer's port still shut (SELinux, another program on it):
                # everything put back and nginx read again - refused, not "done".
                put_back(snap)
                subprocess.run(['systemctl', 'reload', 'nginx'], capture_output=True)
                raise Refused('nginx does not listen on the balancer\'s port %d after the reload '
                              '(SELinux: ausearch -m avc -ts recent; or another program has it) - '
                              'nginx is as it was' % lb_look)
    except BaseException:
        put_back(snap)
        raise
    return said, dh


def vip_part(r, last):
    said = []
    v = r['vip']
    if not v['on']:
        if ka_ours():
            if not NO_SERVICES:
                subprocess.run(['systemctl', 'disable', '--now', 'keepalived'],
                               capture_output=True)
            os.unlink(KA_CONF)
            said.append('keepalived stopped and its file taken away - the web address is on '
                        'no node')
        if last.get('peer'):
            said.append(firewall(last['peer'], int(last.get('family') or 4), False))
        return said, {}
    if ka_ours() is False:
        raise Refused('%s is there and is not otp\'s: keepalived on this machine is used for '
                      'something else. Move that away first.' % KA_CONF)
    progress('keepalived: the web address', 5)
    said.append('keepalived: %s' % keepalived_installed())
    if not v['iface']:
        v['iface'] = iface_of(v['own'], v.get('address') or '')
    elif not os.path.isdir('/sys/class/net/%s' % v['iface']):
        raise Refused('there is no interface %s on this node' % v['iface'])
    if not os.access(CHECK, os.X_OK):
        raise Refused('%s is missing - install.sh --upgrade puts it in' % CHECK)
    snap = snapshot([KA_CONF])
    write_root(KA_CONF, ka_conf(r['node'], v), 0o640)
    if shutil.which('keepalived') and not NO_SERVICES:
        t = subprocess.run(['keepalived', '-t', '-f', KA_CONF], capture_output=True, text=True)
        if t.returncode != 0:
            put_back(snap)
            raise Refused('keepalived does not take the file: %s'
                          % (t.stderr or t.stdout).strip()[-300:])
    said.append('keepalived: %s on %s, VRRP id %d, with %s'
                % (v['address'], v['iface'], v['vrid'], v['peer']))
    if last.get('peer') and last['peer'] != v['peer']:
        firewall(last['peer'], int(last.get('family') or 4), False)
    said.append(firewall(v['peer'], v['family'], True))
    if not NO_SERVICES:
        active = subprocess.run(['systemctl', 'is-active', '--quiet', 'keepalived']).returncode == 0
        subprocess.run(['systemctl', 'enable', 'keepalived'], capture_output=True)
        run(['systemctl', 'reload' if active else 'start', 'keepalived'],
            'systemctl %s keepalived' % ('reload' if active else 'start'))
        said.append('keepalived %s' % ('read its file again' if active else 'started'))
    return said, {'peer': v['peer'], 'family': v['family'], 'iface': v['iface']}


# ---- the local firewall (1.0.52) ----------------------------------------------------
# Everything otp opens is in a chain of its own, OTP-IN, jumped to first from
# INPUT - for IPv4 (iptables) and IPv6 (ip6tables). The rules already on the
# machine are left exactly as they are: otp's chain only adds to them. With
# iptables-services the chain is also written into /etc/sysconfig/iptables
# and ip6tables (between marks of its own, the rest of the file untouched,
# its comments kept), so it is there after a reboot.
FW_CHAIN = 'OTP-IN'
FW_FILES = {4: os.environ.get('OTP_FW_FILE4', '/etc/sysconfig/iptables'),
            6: os.environ.get('OTP_FW_FILE6', '/etc/sysconfig/ip6tables')}
FW_TOOLS = {4: ('iptables', 'iptables-restore', 'iptables-save'),
            6: ('ip6tables', 'ip6tables-restore', 'ip6tables-save')}
FW_PROTOS = ('tcp', 'udp', 'icmp', 'vrrp', 'any')
FW_MARK = '# otp:'


def fw_backend():
    if not NO_SERVICES and shutil.which('firewall-cmd') and \
            subprocess.run(['firewall-cmd', '--state'], capture_output=True).returncode == 0:
        return 'firewalld'
    if shutil.which('iptables'):
        return 'iptables'
    return ''


def fw_rule_checked(x):
    if not isinstance(x, dict):
        raise Refused('a firewall rule is not an object')
    fam = int(x.get('family') or 0)
    if fam not in (4, 6):
        raise Refused('a firewall rule is for IPv4 or IPv6')
    proto = str(x.get('proto') or 'any')
    if proto not in FW_PROTOS:
        raise Refused('the protocol is one of %s' % ', '.join(FW_PROTOS))
    port = str(x.get('port') or '').replace(' ', '')
    if port:
        if proto not in ('tcp', 'udp'):
            raise Refused('a port is for TCP or UDP')
        parts = port.split(',')
        # A range counts as two, as iptables counts it; matched whole - $
        # let a newline at the end through (1.0.59).
        if sum(2 if '-' in p else 1 for p in parts) > 15 or \
                not all(re.fullmatch(r'[0-9]{1,5}(-[0-9]{1,5})?', p) for p in parts):
            raise Refused('the ports are numbers or ranges, by commas: 80,443 or 1812-1813')
        for p in parts:
            a, _, b = p.partition('-')
            if not 1 <= int(a) <= 65535 or (b and not int(a) <= int(b) <= 65535):
                raise Refused('%s is not a port or a range of them' % p)
    src = str(x.get('source') or '').strip()
    if src:
        try:
            net = plain(src, 'network')
        except ValueError:
            raise Refused('%r is not an address or a network' % src[:60])
        if net.version != fam:
            raise Refused('%s is not an IPv%d address' % (src, fam))
        src = str(net)
    action = str(x.get('action') or 'accept')
    if action not in ('accept', 'drop', 'reject'):
        raise Refused('a rule accepts, drops or rejects')
    note = re.sub(r'[^A-Za-z0-9 ._:/@()+,-]', '', str(x.get('note') or ''))[:120]
    return {'family': fam, 'proto': proto, 'port': port, 'source': src, 'action': action,
            'note': note}


def fw_args(r):
    a = ['-A', FW_CHAIN]
    if r['source']:
        a += ['-s', r['source']]
    if r['proto'] != 'any':
        proto = 'ipv6-icmp' if (r['proto'] == 'icmp' and r['family'] == 6) else r['proto']
        a += ['-p', proto]
    if r['port']:
        if ',' in r['port']:
            a += ['-m', 'multiport', '--dports', r['port'].replace('-', ':')]
        else:
            a += ['--dport', r['port'].replace('-', ':')]
    a += ['-m', 'comment', '--comment', '"otp: %s"' % (r['note'] or r['proto'])]
    if r['action'] == 'reject':
        a += ['-j', 'REJECT']
    else:
        a += ['-j', r['action'].upper()]
    return ' '.join(a)


def fw_strip(text):
    """A saved ruleset without anything otp put in it."""
    out = []
    for line in text.split('\n'):
        # iptables-save -c puts the counters first: [12:3456] -A INPUT ...
        k = re.sub(r'^\[\d+:\d+\]\s+', '', line.strip())
        if k.startswith(FW_MARK) or re.match(r'^:%s - \[\d+:\d+\]\Z' % FW_CHAIN, k) or \
                k == '-A INPUT -j %s' % FW_CHAIN or k.startswith('-A %s ' % FW_CHAIN):
            continue
        out.append(line)
    return '\n'.join(out)


def fw_into(text, lines, on):
    """otp's chain into a saved ruleset (iptables-services' file), in the
    *filter table: its name, the jump from INPUT first, its rules last."""
    text = fw_strip(text)
    if not on:
        return text
    rows = text.split('\n')
    try:
        start = next(i for i, l in enumerate(rows) if l.strip() == '*filter')
    except StopIteration:
        rows += ['*filter', ':INPUT ACCEPT [0:0]', ':FORWARD ACCEPT [0:0]',
                 ':OUTPUT ACCEPT [0:0]', 'COMMIT']
        start = len(rows) - 5
    end = next((i for i in range(start + 1, len(rows)) if rows[i].strip() == 'COMMIT'), None)
    if end is None:
        raise Refused('the saved firewall has a *filter table without COMMIT')
    last_decl = max([i for i in range(start, end) if rows[i].startswith(':')] or [start])
    first_input = next((i for i in range(start, end) if rows[i].startswith('-A INPUT')), end)
    block = ['%s otp opens what its functions need here (Settings - Firewall); changed '
             'only there' % FW_MARK] + lines + ['%s end' % FW_MARK]
    rows = (rows[:last_decl + 1] + [':%s - [0:0]' % FW_CHAIN] +
            rows[last_decl + 1:first_input] +
            ['%s every rule otp makes is in %s' % (FW_MARK, FW_CHAIN), '-A INPUT -j %s' % FW_CHAIN] +
            rows[first_input:end] + block + rows[end:])
    return '\n'.join(rows)


FW_ASK = 'fw.ask'
FW_NOW = 'fwnow.json'


def fw_full(fam):
    """The whole filter table as iptables-save shows it (1.0.67): INPUT,
    OTP-IN and every other chain, counters and comments left out."""
    tool = FW_TOOLS[fam][2]
    if not shutil.which(tool):
        return []
    got = subprocess.run([tool, '-t', 'filter'], capture_output=True, text=True)
    out = []
    for line in got.stdout.split('\n'):
        line = re.sub(r'^\[\d+:\d+\]\s+', '', line.strip())
        if not line or line.startswith('#') or line in ('*filter', 'COMMIT'):
            continue
        out.append(re.sub(r' \[\d+:\d+\]$', '', line))
    return out[:1500]


def drop_ask(name, d):
    """An asking file taken away, whatever the otp account made of it
    (1.0.94): a link (refused by O_NOFOLLOW) or a folder was never removed,
    the path unit started this service again and again until systemd gave
    up - and with it every later TLS, VIP and firewall change."""
    try:
        os.unlink(name, dir_fd=d)
        return
    except FileNotFoundError:
        return
    except OSError:
        pass
    try:
        os.rmdir(name, dir_fd=d)
        return
    except OSError:
        pass
    try:
        os.rename(name, '.refused-%s-%d' % (name, int(time.time())), src_dir_fd=d, dst_dir_fd=d)
    except OSError:
        pass


def fw_read_part(force=False):
    """The firewall as it is now, written for the pages (1.0.67): when they
    ask for it, and after every change made here."""
    d = web_fd()
    if not force:
        try:
            read_req(FW_ASK, 4096)
        except FileNotFoundError:
            return
        except (Refused, OSError):
            pass
        drop_ask(FW_ASK, d)
    backend = fw_backend()
    out = {'at': time.time(), 'backend': backend,
           'full': {4: fw_full(4), 6: fw_full(6)} if backend == 'iptables' else {}}
    if backend == 'firewalld' and shutil.which('firewall-cmd'):
        got = subprocess.run(['firewall-cmd', '--list-all'], capture_output=True, text=True)
        out['full'] = {4: [x.rstrip() for x in got.stdout.split('\n') if x.strip()][:400], 6: []}
    write_here(FW_NOW, json.dumps(out))


def fw_now(fam):
    """What the machine's INPUT holds now, otp's chain apart - shown on the
    pages as what else is in the firewall."""
    tool = FW_TOOLS[fam][2]
    if not shutil.which(tool):
        return []
    got = subprocess.run([tool, '-t', 'filter'], capture_output=True, text=True)
    out = []
    for line in got.stdout.split('\n'):
        if line.startswith(':INPUT ') or (line.startswith('-A INPUT') and
                                           line.strip() != '-A INPUT -j %s' % FW_CHAIN):
            out.append(line.strip())
    return out[:200]


def fw_base(fam):
    """What the chain lets through before anybody's rule (1.0.59): the
    machine's own loopback, the answers to what it asked itself (LDAP, DNS,
    mail, the other node's replication), and on IPv6 the neighbour
    discovery it cannot live without. Ahead of the rules a DROP of somebody's
    shut every one of them out."""
    out = ['-A %s -i lo -m comment --comment "otp: loopback" -j ACCEPT' % FW_CHAIN,
           '-A %s -m conntrack --ctstate ESTABLISHED,RELATED -m comment --comment '
           '"otp: answers" -j ACCEPT' % FW_CHAIN]
    if fam == 6:
        out += ['-A %s -p ipv6-icmp -m icmp6 --icmpv6-type %d -m comment --comment '
                '"otp: neighbour discovery" -j ACCEPT' % (FW_CHAIN, t) for t in (133, 134, 135, 136)]
    return out


def fw_said(stderr):
    """What iptables said, without its last line (1.0.59): that is always
    the hint to read its help."""
    lines = [x.strip() for x in (stderr or '').strip().splitlines()
             if x.strip() and not x.strip().startswith('Try `')]
    return '; '.join(lines[-3:]) or '?'


def fw_apply(f, said):
    for fam in (4, 6):
        tool, restore, _save = FW_TOOLS[fam]
        lines = fw_base(fam) + [fw_args(r) for r in f['rules'] if r['family'] == fam]
        if not shutil.which(tool):
            continue
        if f['on']:
            snippet = '*filter\n:%s - [0:0]\n%s\nCOMMIT\n' % (FW_CHAIN, '\n'.join(lines))
            got = subprocess.run([restore, '--noflush'], input=snippet, capture_output=True,
                                 text=True)
            if got.returncode != 0:
                raise Refused('%s does not take the rules: %s' % (restore, fw_said(got.stderr)))
            if subprocess.run([tool, '-C', 'INPUT', '-j', FW_CHAIN],
                              capture_output=True).returncode != 0:
                subprocess.run([tool, '-I', 'INPUT', '1', '-j', FW_CHAIN], capture_output=True)
            said.append('IPv%d: %d rule(s) in %s' % (fam, len(lines), FW_CHAIN))
        else:
            while subprocess.run([tool, '-D', 'INPUT', '-j', FW_CHAIN],
                                 capture_output=True).returncode == 0:
                pass
            subprocess.run([tool, '-F', FW_CHAIN], capture_output=True)
            subprocess.run([tool, '-X', FW_CHAIN], capture_output=True)
        # Kept over a reboot, where iptables-services keeps the rules.
        path = FW_FILES[fam]
        if os.path.exists(path):
            with open(path) as fh:
                old = fh.read()
            new = fw_into(old, lines, f['on'])
            if new != old:
                fd, tmp = tempfile.mkstemp(prefix='.otp-fw-', dir=os.path.dirname(path))
                with os.fdopen(fd, 'w') as fh:
                    fh.write(new if new.endswith('\n') else new + '\n')
                test = subprocess.run([restore, '--test', tmp], capture_output=True, text=True)
                if test.returncode != 0:
                    os.unlink(tmp)
                    raise Refused('%s would not take the file, so it was left as it was: %s' % (
                        restore, fw_said(test.stderr)))
                os.chmod(tmp, os.stat(path).st_mode & 0o777)
                os.replace(tmp, path)
                if shutil.which('restorecon'):
                    subprocess.run(['restorecon', path], capture_output=True)
                said.append('%s: kept over a reboot' % path)
        elif f['on']:
            said.append('IPv%d: not kept over a reboot - %s is not there (dnf install '
                        'iptables-services)' % (fam, path))


def fw_part(f):
    """The firewall as asked: (words, report)."""
    said = []
    backend = fw_backend()
    report = {'backend': backend, 'now': {4: fw_now(4), 6: fw_now(6)} if backend == 'iptables'
              else {}}
    if f is None:
        return said, report
    if backend == 'firewalld':
        if f['on']:
            raise Refused('firewalld manages this machine\'s firewall: otp leaves it to it (what '
                          'to open is in docs/tls-and-vip.md). To manage it here, use iptables '
                          '(dnf install iptables-services; systemctl disable --now firewalld; '
                          'systemctl enable --now iptables ip6tables)')
        return said, report
    if not backend:
        if f['on']:
            raise Refused('there is no iptables on this machine')
        return said, report
    progress('the firewall', 5)
    # As it was, live and in the files, to go back to when anything fails
    # half way (1.0.57) - never a machine left half done.
    was_live, was_file = {}, {}
    for fam in (4, 6):
        if shutil.which(FW_TOOLS[fam][2]):
            was_live[fam] = subprocess.run([FW_TOOLS[fam][2]], capture_output=True,
                                           text=True).stdout
        if os.path.exists(FW_FILES[fam]):
            was_file[fam] = snapshot([FW_FILES[fam]])
    try:
        fw_apply(f, said)
    except BaseException:
        for fam, text in was_live.items():
            if text.strip():
                subprocess.run([FW_TOOLS[fam][1]], input=text, capture_output=True, text=True)
            else:
                # Nothing there before (1.0.59): what was put in is taken out
                # again, not left live under a "failed".
                tool = FW_TOOLS[fam][0]
                while subprocess.run([tool, '-D', 'INPUT', '-j', FW_CHAIN],
                                     capture_output=True).returncode == 0:
                    pass
                subprocess.run([tool, '-F', FW_CHAIN], capture_output=True)
                subprocess.run([tool, '-X', FW_CHAIN], capture_output=True)
        for snap in was_file.values():
            put_back(snap)
        raise
    if not f['on']:
        said.append('the firewall: otp\'s rules taken away; the rest is as it was')
    report['now'] = {4: fw_now(4), 6: fw_now(6)}
    try:
        fw_read_part(force=True)
    except Exception:                                   # noqa: BLE001
        pass
    return said, report


# ---- PostgreSQL's log, for the replication errors on the pages (1.0.52) -------------
# The log is postgres's (0600): the otp account asks for it with pglog.ask,
# root reads only the lines about logical replication and writes them into
# pglog.json, which the otp group may read. Nothing else is taken from it.
PGLOG_GLOBS = ('/var/lib/pgsql/*/data/log/*.log', '/var/lib/pgsql/data/log/*.log',
               '/var/lib/pgsql/*/data/pg_log/*.log', '/var/log/postgresql/*.log')
PGLOG_WORDS = re.compile(r'logical replication|subscription|apply worker|tablesync|'
                         r'publication|replication slot|replication origin|otp_from_|'
                         r'processing remote data|walsender|wal_status', re.I)
PG_LINE = re.compile(r'^(\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d)(?:\.\d+)?\s*([A-Z]{2,5}|[+-]\d\d(?::?\d\d)?)?\b')


def pg_time(stamp, zone):
    """A log line's time with its zone (1.0.59): UTC, or +02 / +0200, kept
    as said; a name it does not know (CEST) read as this machine's own."""
    tm = time.strptime(stamp.replace('T', ' '), '%Y-%m-%d %H:%M:%S')
    zone = (zone or '').strip()
    import calendar
    if zone in ('UTC', 'GMT', 'Z'):
        return float(calendar.timegm(tm))
    m = re.fullmatch(r'([+-])(\d\d):?(\d\d)?', zone)
    if m:
        off = (int(m.group(2)) * 60 + int(m.group(3) or 0)) * 60
        return float(calendar.timegm(tm)) - (off if m.group(1) == '+' else -off)
    return time.mktime(tm)
PG_LEVEL = re.compile(r'\b(ERROR|FATAL|PANIC|WARNING|LOG|DETAIL|CONTEXT|HINT|STATEMENT):\s\s?(.*)$')


def pglog_files(port):
    import glob
    found = []
    if not NO_SERVICES and shutil.which('runuser') and shutil.which('psql'):
        got = subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', str(int(port)),
                              '-XAtc', "SELECT current_setting('data_directory'), "
                              "pg_current_logfile()"],
                             capture_output=True, text=True, timeout=10, cwd='/')
        parts = (got.stdout or '').strip().split('|')
        if got.returncode == 0 and len(parts) == 2 and parts[1]:
            f = parts[1] if parts[1].startswith('/') else os.path.join(parts[0], parts[1])
            folder = os.path.dirname(f)
            found = [os.path.join(folder, x) for x in os.listdir(folder)
                     if x.endswith('.log')] if os.path.isdir(folder) else [f]
    if not found:
        for g in PGLOG_GLOBS:
            found += glob.glob(g)
    # Plain files of PostgreSQL's own only (1.0.59): root reads them, and
    # a link in a folder anybody writes to could point at anything.
    try:
        import pwd
        pg_uid = pwd.getpwnam('postgres').pw_uid
    except (KeyError, ImportError):
        pg_uid = None
    good = []
    for f in set(found):
        try:
            st = os.lstat(f)
        except OSError:
            continue
        if stat.S_ISREG(st.st_mode) and (pg_uid is None or st.st_uid == pg_uid):
            good.append(f)
    good.sort(key=lambda f: os.lstat(f).st_mtime)
    return good[-3:]


def pg_owner():
    try:
        import pwd
        return pwd.getpwnam('postgres').pw_uid
    except (KeyError, ImportError):
        return None


def pglog_part():
    d = web_fd()
    try:
        raw = read_req(PGLOG_ASK, 4096)
    except FileNotFoundError:
        return
    except (Refused, OSError):
        drop_ask(PGLOG_ASK, d)
        return
    drop_ask(PGLOG_ASK, d)
    try:
        port = int(json.loads(raw.decode('utf-8')).get('port') or 5432)
    except (ValueError, TypeError, AttributeError):
        port = 5432
    out = {'at': time.time(), 'entries': [], 'file': '', 'said': ''}
    try:
        files = pglog_files(port)
        if not files:
            out['said'] = 'PostgreSQL\'s log was not found (log_destination stderr with ' \
                          'logging_collector on writes it into data/log)'
        entries, cur = [], None
        for path in files:
            out['file'] = path
            with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as f:
                # What was opened, checked again (1.0.94): the file looked at
                # and the one opened could differ in between.
                fst = os.fstat(f.fileno())
                if not stat.S_ISREG(fst.st_mode) or (pg_owner() is not None and
                                                      fst.st_uid != pg_owner()):
                    continue
                size = fst.st_size
                f.seek(max(0, size - 4 * 1024 * 1024))
                text = f.read().decode('utf-8', 'replace')
            for line in text.split('\n'):
                m = PG_LEVEL.search(line)
                if not m:
                    if cur is not None and line.startswith(('\t', ' ')):
                        cur['text'] += ' ' + line.strip()
                    continue
                level, said = m.group(1), m.group(2).strip()
                if level == 'STATEMENT':
                    continue        # the statement may hold data: never handed on (1.0.57)
                if level in ('DETAIL', 'CONTEXT', 'HINT'):
                    if cur is not None:
                        cur.setdefault('more', []).append('%s: %s' % (level, said[:600]))
                    continue
                if cur is not None:
                    entries.append(cur)
                cur = None
                if level in ('ERROR', 'FATAL', 'PANIC', 'WARNING') or \
                        (level == 'LOG' and PGLOG_WORDS.search(said)):
                    ts = None
                    t = PG_LINE.match(line)
                    if t:
                        try:
                            ts = pg_time(t.group(1), t.group(2))
                        except ValueError:
                            ts = None
                    cur = {'ts': ts, 'level': level, 'text': said[:1000]}
            if cur is not None:
                entries.append(cur)
                cur = None
        keep = [e for e in entries if PGLOG_WORDS.search(e['text'] + ' ' +
                                                         ' '.join(e.get('more') or []))]
        # A statement logged (log_statement ddl/all: CREATE SUBSCRIPTION ... password=...) never
        # handed on, nor any password in what is (1.0.249).
        keep = [e for e in keep if not re.match(r'(?i)(statement|duration|execute)\b', e['text'])]
        for e in keep:
            e['text'] = PG_PW_RE.sub(r'\1***', e['text'])
            if e.get('more'):
                e['more'] = [PG_PW_RE.sub(r'\1***', x) for x in e['more']]
        out['entries'] = keep[-200:]
    except Exception as e:                              # noqa: BLE001
        out['said'] = 'PostgreSQL\'s log could not be read: %s' % str(e)[:200]
    write_here(PGLOG_FILE, json.dumps(out))


# ---- the link between the two databases, encrypted and checked (1.0.104) ----------
# The daemon makes this node's PostgreSQL a certificate from the cluster's own
# authority; this puts it in as root: the key and the certificate into the
# data folder (postgres's, 0600), the authorities into HA_CA_FILE (0644 - they
# are public, and PostgreSQL's replication workers read it), ssl on through
# ALTER SYSTEM and a reload - nothing restarts. Asked for later, the other
# node's lines in pg_hba.conf from host to hostssl. Every value is checked;
# the running server is asked over TLS whether it answers with the new
# certificate before "done" is said.
def pg_sql(port, sql, db='postgres'):
    for runner in (['runuser', '-u', 'postgres', '--'], ['sudo', '-u', 'postgres']):
        if shutil.which(runner[0]):
            got = subprocess.run(runner + ['psql', '-XAtq', '-p', str(int(port)), '-d', db,
                                           '-v', 'ON_ERROR_STOP=1', '-f', '-'],
                                 capture_output=True, text=True, timeout=60,
                                 input=sql.rstrip().rstrip(';') + ';\n')
            if got.returncode == 0:
                return got.stdout.strip()
            raise Refused('PostgreSQL said: %s' % (got.stderr or got.stdout).strip()[:300])
    raise Refused('neither runuser nor sudo is on this machine')


def pg_lit(v):
    return "'%s'" % str(v).replace("'", "''")


def pg_answers_with(port, cert_pem, ca_file):
    """The certificate this PostgreSQL shows over TLS, checked against the
    authorities - True when it is `cert_pem`."""
    import socket
    import ssl
    want = ssl.PEM_cert_to_DER_cert(cert_pem.strip() + '\n')
    ctx = ssl.create_default_context(cafile=ca_file)
    ctx.check_hostname = False          # the names are the other node's matter: verify-full
    s = socket.create_connection(('127.0.0.1', int(port)), timeout=5)
    try:
        s.sendall(b'\x00\x00\x00\x08\x04\xd2\x16\x2f')     # SSLRequest
        if s.recv(1) != b'S':
            return False
        t = ctx.wrap_socket(s)
        try:
            return t.getpeercert(True) == want
        finally:
            t.close()
    finally:
        try:
            s.close()
        except OSError:
            pass


def pg_peer_net(text):
    import ipaddress as _ip
    a = _ip.ip_address(str(text).strip())
    return '%s/%d' % (a, 32 if a.version == 4 else 128)


def pgtls_checked(r):
    if not isinstance(r, dict):
        raise Refused('the request is not an object')
    out = {'id': str(r.get('id') or '')}
    if not re.match(r'^[0-9a-f]{8,40}\Z', out['id']):
        raise Refused('the request has no id')
    out['do'] = r.get('do')
    if out['do'] not in ('server', 'hba', 'peer', 'hba_off', 'server_off', 'listen'):
        raise Refused('server, hba, peer, hba_off, server_off or listen')
    try:
        out['port'] = int(r.get('port') or 5432)
    except (TypeError, ValueError):
        raise Refused('the port is a number')
    if not 1 <= out['port'] <= 65535:
        raise Refused('the port is 1 to 65535')
    for k in ('db', 'user'):
        if not PG_NAME_RE.match(str(r.get(k) or '')):
            raise Refused('the database and its account are plain names')
        # pg_hba's words for "every one" are not otp's
        # database or account (1.0.209): "all all" let any role in from the peer.
        if str(r[k]).lower() in PG_HBA_WORDS:
            raise Refused('%s is a word of pg_hba.conf, not otp\'s database or account' % r[k])
        out[k] = str(r[k])
    # Never the superuser, nor the system's own databases (1.0.248): "peer" put
    # "host postgres postgres ADDRESS" first in pg_hba.conf and opened it to the network.
    if out['db'].lower() in ('postgres', 'template0', 'template1') or out['user'].lower() == 'postgres':
        raise Refused('%s / %s is PostgreSQL\'s own, not otp\'s database and account' % (out['db'], out['user']))
    if out['do'] in ('hba', 'peer'):
        try:
            sup = pg_sql(out['port'], "SELECT rolsuper FROM pg_roles WHERE rolname = '%s'"
                         % out['user'].replace("'", "''"))
        except (Refused, OSError, subprocess.SubprocessError):
            sup = ''
        if sup.strip() == 't':
            raise Refused('%s is a superuser of PostgreSQL - not let in from the network by otp' % out['user'])
    peer = str(r.get('peer') or '').strip()
    try:
        out['peer'] = str(plain(peer, 'address')) if peer else ''
    except ValueError:
        raise Refused('the other node\'s address is one plain address')
    if out['do'] == 'peer':
        try:
            out['old_peer'] = str(plain(str(r.get('old_peer') or '').strip(), 'address')) \
                if r.get('old_peer') else ''
        except ValueError:
            raise Refused('the other node\'s old address is one plain address')
        if not out['peer']:
            raise Refused('the other node\'s new address is needed')
        out['keep_old'] = bool(r.get('keep_old'))
        out['drop_old'] = bool(r.get('drop_old'))
    if str(r.get('ca_file') or HA_CA_FILE) != HA_CA_FILE:
        raise Refused('the authorities go into %s' % HA_CA_FILE)
    if out['do'] == 'server':
        pem = pem_set(r.get('cert'), r.get('key'))
        if not pem:
            raise Refused('the certificate and its key are missing')
        out['cert'], out['key'] = pem['cert'], pem['key']
        trust = str(r.get('trust') or '').strip()
        certs = re.findall(r'-----BEGIN CERTIFICATE-----[A-Za-z0-9+/=\s]+?-----END CERTIFICATE-----',
                           trust)
        if not certs or len(certs) > 5 or sum(len(c) for c in certs) < len(trust) - 20:
            raise Refused('the authorities are PEM certificates')
        with tempfile.TemporaryDirectory(prefix='otp-pgtls-') as t:
            cf = os.path.join(t, 'ca.pem')
            with open(cf, 'w') as f:
                f.write('\n'.join(certs) + '\n')
            sf = os.path.join(t, 'c.pem')
            with open(sf, 'w') as f:
                f.write(out['cert'])
            openssl(['verify', '-CAfile', cf, sf], 'the certificate is not from these authorities')
        out['trust'] = '\n'.join(certs) + '\n'
    return out


def pgtls_listen(r):
    """PostgreSQL listening on the network for the second node of a cluster
    (1.0.213): a bundle made on the pages left it on localhost alone, and the join
    said "Connection refused". listen_addresses = '*', and PostgreSQL started again
    - asked for on the page, which says it restarts it."""
    now = pg_sql(r['port'], 'SHOW listen_addresses').strip()
    if now == '*' or (r.get('peer') and now not in ('', 'localhost', '127.0.0.1', '::1')):
        return {'said': 'PostgreSQL listens on the network already (listen_addresses = %s)' % now}
    pg_sql(r['port'], "ALTER SYSTEM SET listen_addresses = '*'")
    units = []
    if shutil.which('systemctl'):
        got = subprocess.run(['systemctl', 'list-units', '--type=service', '--state=active',
                              '--plain', '--no-legend', '--no-pager', 'postgresql*'],
                             capture_output=True, text=True, timeout=10)
        units = [l.split()[0] for l in got.stdout.splitlines()
                 if l.split() and re.match(r'^postgresql(-\d+)?(@[\w.-]+)?\.service\Z', l.split()[0])]
    if len(units) != 1 or NO_SERVICES:
        return {'said': 'listen_addresses = * is set; PostgreSQL takes it at its next start - '
                        'restart it:  systemctl restart postgresql', 'restart': True}
    got = subprocess.run(['systemctl', 'restart', units[0]], capture_output=True, text=True,
                         timeout=120)
    if got.returncode != 0:
        raise Refused('%s did not start again: %s' % (units[0], (got.stderr or '').strip()[-200:]))
    for _ in range(30):
        try:
            if pg_sql(r['port'], 'SHOW listen_addresses').strip() == '*':
                return {'said': '%s started again: it listens on the network (listen_addresses = *)'
                                % units[0]}
        except Refused:
            pass
        time.sleep(1)
    raise Refused('%s was restarted and does not answer yet - look:  systemctl status %s'
                  % (units[0], units[0]))


def pgtls_server(r):
    data = pg_sql(r['port'], 'SHOW data_directory')
    if not data.startswith('/') or not os.path.isdir(data):
        raise Refused('PostgreSQL\'s data folder was not found (%s)' % data[:100])
    uid = pg_owner()
    gid = None
    try:
        import pwd
        gid = pwd.getpwnam('postgres').pw_gid
    except (KeyError, ImportError):
        pass
    # As it was, for a certificate PostgreSQL does not take (1.0.209): ssl = on
    # and the new files stayed, and its next restart could fail on them.
    was_conf = {}
    for k in ('ssl_cert_file', 'ssl_key_file', 'ssl'):
        got = pg_sql(r['port'], "SELECT setting || '|' || COALESCE(sourcefile, '') FROM "
                                "pg_settings WHERE name = %s" % pg_lit(k))
        was_conf[k] = got.split('|', 1) if '|' in got else [got, '']
    was_files = {}
    for name in ('otp-ha.key', 'otp-ha.crt'):
        # Never through a link, only postgres's own plain file (1.0.249): put back after a
        # change that did not take, a link to /etc/shadow became a file postgres could read.
        try:
            p = os.path.join(data, name)
            st = os.lstat(p)
            was_files[name] = pg_file_read(p) if (stat.S_ISREG(st.st_mode) and
                                                  st.st_uid == uid) else None
        except (OSError, Refused):
            was_files[name] = None
    for name, text, mode in (('otp-ha.key', r['key'], 0o600), ('otp-ha.crt', r['cert'], 0o644)):
        path = os.path.join(data, name)
        pg_file_put(path, text, mode, uid, gid)
    os.makedirs(os.path.dirname(HA_CA_FILE), mode=0o755, exist_ok=True)
    os.chmod(os.path.dirname(HA_CA_FILE), 0o755)
    write_root(HA_CA_FILE, r['trust'], 0o644)
    if shutil.which('restorecon'):
        subprocess.run(['restorecon', '-R', os.path.dirname(HA_CA_FILE),
                        os.path.join(data, 'otp-ha.key'), os.path.join(data, 'otp-ha.crt')],
                       capture_output=True)
    pg_sql(r['port'], 'ALTER SYSTEM SET ssl_cert_file = %s' % pg_lit(os.path.join(data, 'otp-ha.crt')))
    pg_sql(r['port'], 'ALTER SYSTEM SET ssl_key_file = %s' % pg_lit(os.path.join(data, 'otp-ha.key')))
    pg_sql(r['port'], "ALTER SYSTEM SET ssl = 'on'")
    pg_sql(r['port'], 'SELECT pg_reload_conf()')
    seen = False
    for _ in range(20):
        time.sleep(0.5)
        try:
            if pg_answers_with(r['port'], r['cert'], HA_CA_FILE):
                seen = True
                break
        except Exception:                               # noqa: BLE001
            pass
    if not seen:
        try:
            for k, (setting, src) in was_conf.items():
                if src.endswith('postgresql.auto.conf'):
                    pg_sql(r['port'], 'ALTER SYSTEM SET %s = %s' % (k, pg_lit(setting)))
                else:
                    pg_sql(r['port'], 'ALTER SYSTEM RESET %s' % k)
            for name, old in was_files.items():
                path = os.path.join(data, name)
                if old is None:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
                else:
                    pg_file_put(path, old, 0o600 if name.endswith('.key') else 0o644, uid, gid)
            pg_sql(r['port'], 'SELECT pg_reload_conf()')
        except Exception:                               # noqa: BLE001
            pass
        raise Refused('PostgreSQL did not take the certificate on reload - its log says why '
                      '(Settings → High availability → The errors); it is as it was')
    end = openssl(['x509', '-noout', '-enddate'], 'the certificate', r['cert'])
    import ssl as _ssl
    return {'said': 'PostgreSQL answers over TLS with its certificate from the cluster\'s '
                    'authority', 'data_dir': data,
            'cert_end': float(_ssl.cert_time_to_seconds(end.strip().split('=', 1)[-1]))}


def pg_hba_file(port):
    """pg_hba.conf as PostgreSQL names it - only a file of postgres's own, not a link (1.0.252):
    whatever answered on PostgreSQL's socket said which file root rewrote, /etc/shadow as well."""
    hba = pg_sql(port, 'SHOW hba_file')
    if not hba.startswith('/') or not os.path.isfile(hba):
        raise Refused('pg_hba.conf was not found (%s)' % hba[:100])
    try:
        st = os.lstat(hba)
    except OSError as e:
        raise Refused('pg_hba.conf cannot be read: %s' % e)
    owner = pg_owner()
    if not stat.S_ISREG(st.st_mode) or owner is None or st.st_uid != owner:
        raise Refused('%s is not a file of the account postgres - not changed' % hba[:100])
    return hba


def pgtls_hba(r):
    if not r['peer']:
        raise Refused('the other node\'s address is not known here')
    net = pg_peer_net(r['peer'])
    if net.startswith('127.') or net == '::1/128':
        return {'said': 'the other node is on this machine (%s): its line in pg_hba.conf is '
                        'this node\'s own, left as it is' % r['peer']}
    hba = pg_hba_file(r['port'])
    text = pg_file_read(hba)        # not through a link (1.0.149)
    lines, changed, have_ssl = text.split('\n'), 0, False
    for i, line in enumerate(lines):
        f = line.split()
        if len(f) >= 5 and f[1] == r['db'] and f[2] == r['user'] and f[3] == net:
            if f[0] == 'host':
                lines[i] = re.sub(r'^host(\s)', r'hostssl\1', line, count=1)
                changed += 1
            elif f[0] == 'hostssl':
                have_ssl = True
    if not changed:
        if have_ssl:
            return {'said': 'pg_hba.conf already takes the other node over TLS only'}
        raise Refused('pg_hba.conf has no line of otp\'s for %s (%s %s): it was written by '
                      'hand - change host to hostssl there yourself' % (net, r['db'], r['user']))
    st = os.lstat(hba)
    pg_file_copy(hba, hba + '.otp-before-tls')
    pg_file_put(hba, '\n'.join(lines), stat.S_IMODE(st.st_mode), st.st_uid, st.st_gid)
    try:
        pg_sql(r['port'], 'SELECT pg_reload_conf()')
        bad = pg_sql(r['port'], 'SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL')
        if bad not in ('', '0'):
            raise Refused('PostgreSQL does not read pg_hba.conf as written')
    except Refused:
        pg_file_copy(hba + '.otp-before-tls', hba)
        pg_sql(r['port'], 'SELECT pg_reload_conf()')
        raise
    return {'said': 'the other node (%s) is let into the database over TLS only (hostssl)'
                    % r['peer']}


def pgtls_peer(r):
    """The other node moved to another address (1.0.106): otp's line for it in
    pg_hba.conf moved with it - host or hostssl as it was - or, with none, a
    host line put in front. The file as it was is kept beside it."""
    net = pg_peer_net(r['peer'])
    old = pg_peer_net(r['old_peer']) if r.get('old_peer') else ''
    hba = pg_hba_file(r['port'])
    text = pg_file_read(hba)        # not through a link (1.0.149)
    lines, moved, there = text.split('\n'), 0, False

    def ours(f):
        return len(f) >= 5 and f[0] in ('host', 'hostssl') and f[1] == r['db'] and \
            f[2] == r['user']
    # The old one the same as the new (1.0.262): nothing old to take out - a Keep of a network whose
    # IPv4 address did not change (its gateway, DNS, name) asked drop_old, and the node's own line
    # went, replication from it refused.
    olds = bool(old) and old != net and not old.startswith('127.') and old != '::1/128'
    there = any(ours(line.split()) and line.split()[3] == net for line in lines)
    if r.get('keep_old'):
        # On trial (1.0.137): the new address let in beside the old one.
        if not there:
            for i, line in enumerate(lines):
                f = line.split()
                if olds and ours(f) and f[3] == old:
                    lines.insert(i + 1, line.replace(old, net, 1))
                    moved += 1
                    there = True
                    break
    elif there or r.get('drop_old'):
        # The new one in already (kept, or going back to one kept beside it):
        # the old line out, not made a second copy of the new.
        if olds:
            keep = [line for line in lines if not (ours(line.split()) and
                                                   line.split()[3] == old)]
            moved = len(lines) - len(keep)
            lines = keep
    else:
        for i, line in enumerate(lines):
            f = line.split()
            if olds and ours(f) and f[3] == old:
                lines[i] = line.replace(old, net, 1)
                moved += 1
                there = True
    if not there:
        lines.insert(0, 'host    %s    %s    %s    scram-sha-256' % (r['db'], r['user'], net))
        lines.insert(0, '# otp high availability: the other node (%s)' % time.strftime('%Y-%m-%d'))
    new_text = '\n'.join(lines)
    if new_text == text:
        return {'said': 'pg_hba.conf already lets %s in' % r['peer']}
    st = os.lstat(hba)
    pg_file_copy(hba, hba + '.otp-before-readdress')
    pg_file_put(hba, new_text, stat.S_IMODE(st.st_mode), st.st_uid, st.st_gid)
    try:
        pg_sql(r['port'], 'SELECT pg_reload_conf()')
        bad = pg_sql(r['port'], 'SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL')
        if bad not in ('', '0'):
            raise Refused('PostgreSQL does not read pg_hba.conf as written')
    except Refused:
        pg_file_copy(hba + '.otp-before-readdress', hba)
        pg_sql(r['port'], 'SELECT pg_reload_conf()')
        raise
    return {'said': 'pg_hba.conf lets the other node in from %s%s' % (
        r['peer'], (' (was %s)' % r['old_peer']) if moved else '')}


def pgtls_hba_off(r):
    """TLS switched off (1.0.107): the other node's hostssl line back to host."""
    if not r['peer']:
        return {'said': 'the other node\'s address is not known here: nothing changed'}
    net = pg_peer_net(r['peer'])
    if net.startswith('127.') or net == '::1/128':
        return {'said': 'the other node is on this machine: nothing changed'}
    hba = pg_hba_file(r['port'])
    text = pg_file_read(hba)        # not through a link (1.0.149)
    lines, changed = text.split('\n'), 0
    for i, line in enumerate(lines):
        f = line.split()
        if len(f) >= 5 and f[0] == 'hostssl' and f[1] == r['db'] and f[2] == r['user'] and \
                f[3] == net:
            lines[i] = re.sub(r'^hostssl(\s)', r'host\1', line, count=1)
            changed += 1
    if not changed:
        return {'said': 'pg_hba.conf already lets the other node in without TLS'}
    st = os.lstat(hba)
    pg_file_copy(hba, hba + '.otp-before-tls-off')
    pg_file_put(hba, '\n'.join(lines), stat.S_IMODE(st.st_mode), st.st_uid, st.st_gid)
    pg_sql(r['port'], 'SELECT pg_reload_conf()')
    return {'said': 'the other node (%s) is let in with or without TLS again' % r['peer']}


def pgtls_server_off(r):
    """TLS switched off (1.0.107): ssl and its files as they were before otp
    (ALTER SYSTEM RESET - postgresql.conf says again), the cluster's key and
    certificate taken out of the data folder, the authority file away."""
    data = pg_sql(r['port'], 'SHOW data_directory')
    for k in ('ssl_cert_file', 'ssl_key_file', 'ssl'):
        pg_sql(r['port'], 'ALTER SYSTEM RESET %s' % k)
    pg_sql(r['port'], 'SELECT pg_reload_conf()')
    time.sleep(1)
    now = pg_sql(r['port'], 'SHOW ssl')
    gone = []
    if data.startswith('/') and os.path.isdir(data):
        for name in ('otp-ha.key', 'otp-ha.crt'):
            try:
                os.unlink(os.path.join(data, name))
                gone.append(name)
            except FileNotFoundError:
                pass
    try:
        os.unlink(HA_CA_FILE)
        gone.append(HA_CA_FILE)
    except FileNotFoundError:
        pass
    return {'said': 'PostgreSQL is as it was before (ssl = %s, by postgresql.conf); taken '
                    'away: %s' % (now, ', '.join(gone) or 'nothing')}


def pgtls_part():
    d = web_fd()
    try:
        raw = read_req(PGTLS_ASK, 65536)
    except FileNotFoundError:
        return
    except (Refused, OSError):
        drop_ask(PGTLS_ASK, d)
        return
    drop_ask(PGTLS_ASK, d)
    out = {'at': time.time(), 'ok': False, 'id': ''}
    try:
        r = json.loads(raw.decode('utf-8'))
        out['id'] = str((r or {}).get('id') or '')[:40] if isinstance(r, dict) else ''
        r = pgtls_checked(r)
        out.update({'server': pgtls_server, 'peer': pgtls_peer, 'hba': pgtls_hba,
                    'hba_off': pgtls_hba_off, 'server_off': pgtls_server_off,
                    'listen': pgtls_listen}[r['do']](r))
        out['ok'] = True
    except Refused as e:
        out['said'] = str(e)[:400]
    except Exception as e:                              # noqa: BLE001
        out['said'] = 'it went wrong: %s' % str(e)[:300]
    write_here(PGTLS_FILE, json.dumps(out))


# ---- the machine's network, its name, and switching it off (1.0.119) ----------------
# Asked in net.ask: what the network is now (read), a new one put in
# NetworkManager with the host name and /etc/hosts (apply), or a reboot or a
# power-off (power). Every value checked here again: addresses by ipaddress,
# names by NAME_RE, the connection by the list NetworkManager gives.
NET_ASK = 'net.ask'
NET_FILE = 'net.json'
NMCLI = os.environ.get('OTP_NMCLI', 'nmcli')
HOSTNAMECTL = os.environ.get('OTP_HOSTNAMECTL', 'hostnamectl')
HOSTS_FILE = os.environ.get('OTP_HOSTS_FILE', '/etc/hosts')
POWER_CMD = os.environ.get('OTP_POWER_CMD', '')        # tests: a file to write instead
# What the machine had before a change on trial (1.0.139): root's alone - the
# otp account may write /etc/otp, and what is put back from here runs as root.
NET_SNAP_DIR = os.environ.get('OTP_NET_SNAP_DIR', '/var/lib/otp-net')
NET_SNAP_FILE = 'before.json'
NET_PROFILE_DIRS = tuple(x for x in os.environ.get(
    'OTP_NM_PROFILE_DIRS', '/etc/NetworkManager/system-connections/:'
    '/etc/sysconfig/network-scripts/:/run/NetworkManager/system-connections/').split(':') if x)
NET_SYSCTL6 = os.environ.get('OTP_SYSCTL6', '/etc/sysctl.d/90-otp-ipv6.conf')


def nm_fields(con, fields):
    out = run([NMCLI, '-t', '-g', ','.join(fields), 'connection', 'show', con],
              'nmcli connection show')
    vals = out.rstrip('\n').split('\n')
    got = {}
    for k, v in zip(fields, vals + [''] * (len(fields) - len(vals))):
        got[k] = v.replace('\\:', ':').strip()
    return got


def nm_list(text):
    return [x.strip() for x in re.split(r'[,\s]+', text or '') if x.strip() and x.strip() != '--']


def net_read():
    out = {'nm': bool(shutil.which(NMCLI)), 'devices': [], 'con': '', 'dev': '', 'conf': {},
           'live': {'addrs4': [], 'addrs6': [], 'gw4': '', 'gw6': '', 'dns': []}}
    try:
        with open('/proc/sys/net/ipv6/conf/all/disable_ipv6') as f:
            out['ipv6_kernel'] = f.read().strip() == '0'
    except OSError:
        out['ipv6_kernel'] = False
    try:
        for line in run(['ip', '-o', 'addr', 'show'], 'ip addr').splitlines():
            f = line.split()
            if len(f) < 4 or f[1] == 'lo':
                continue
            try:
                ifc = ipaddress.ip_interface(f[3])
            except ValueError:
                continue
            if ifc.ip.is_loopback or ifc.ip.is_link_local:
                continue
            (out['live']['addrs4'] if ifc.version == 4 else out['live']['addrs6']).append(
                {'addr': str(ifc), 'dev': f[1].split('@')[0]})
        for fam, key in (('-4', 'gw4'), ('-6', 'gw6')):
            r = run(['ip', fam, 'route', 'show', 'default'], 'ip route', ok=(0, 1, 2))
            m = re.search(r'default via (\S+) dev (\S+)', r)
            if m:
                out['live'][key] = m.group(1)
                if key == 'gw4':
                    out['dev'] = m.group(2)
    except Refused:
        pass
    try:
        with open('/etc/resolv.conf') as f:
            out['live']['dns'] = [l.split()[1] for l in f if l.startswith('nameserver ')
                                  and len(l.split()) > 1][:6]
    except OSError:
        pass
    try:
        out['hostname'] = run([HOSTNAMECTL, '--static'], 'hostnamectl').strip() or \
            os.uname().nodename
    except (Refused, OSError):
        out['hostname'] = os.uname().nodename
    if not out['nm']:
        return out
    try:
        for line in run([NMCLI, '-t', '-f', 'DEVICE,TYPE,STATE,CONNECTION', 'device'],
                        'nmcli device').splitlines():
            f = line.replace('\\:', '\x00').split(':')
            f = [x.replace('\x00', ':') for x in f]
            if len(f) >= 4 and f[1] in ('ethernet', 'bond', 'vlan', 'bridge', 'team', 'wifi'):
                out['devices'].append({'dev': f[0], 'type': f[1], 'state': f[2], 'con': f[3]})
    except Refused as e:
        out['nm_said'] = str(e)
    dev = out['dev'] or next((d['dev'] for d in out['devices'] if d['con']), '')
    con = next((d['con'] for d in out['devices'] if d['dev'] == dev and d['con']), '')
    out['dev'], out['con'] = dev, con
    if con:
        try:
            g = nm_fields(con, ['ipv4.method', 'ipv4.addresses', 'ipv4.gateway', 'ipv4.dns',
                                'ipv4.dns-search', 'ipv6.method', 'ipv6.addresses',
                                'ipv6.gateway', 'ipv6.dns'])
            out['conf'] = {'ipv4_method': g['ipv4.method'],
                           'ipv4_addresses': nm_list(g['ipv4.addresses']),
                           'ipv4_gateway': g['ipv4.gateway'] if g['ipv4.gateway'] != '--' else '',
                           'ipv4_dns': nm_list(g['ipv4.dns']),
                           'ipv4_search': nm_list(g['ipv4.dns-search']),
                           'ipv6_method': g['ipv6.method'],
                           'ipv6_addresses': nm_list(g['ipv6.addresses']),
                           'ipv6_gateway': g['ipv6.gateway'] if g['ipv6.gateway'] != '--' else '',
                           'ipv6_dns': nm_list(g['ipv6.dns'])}
        except Refused as e:
            out['nm_said'] = str(e)
    return out


def net_checked(r):
    """An apply request, every value in its one shape."""
    out = {'con': str(r.get('con') or ''), 'reboot_in': 0}
    if not out['con'] or len(out['con']) > 120 or any(c in out['con'] for c in '\n\r\x00'):
        raise Refused('which connection?')
    v4 = r.get('ipv4') or {}
    try:
        a4 = plain(v4.get('addr'), 'interface')
    except ValueError:
        raise Refused('the IPv4 address is an address with its prefix (192.0.2.10/24)')
    if a4.version != 4 or '/' not in str(v4.get('addr')):
        raise Refused('the IPv4 address is an address with its prefix (192.0.2.10/24)')
    out['addr4'] = str(a4)
    gw = str(v4.get('gw') or '').strip()
    if gw:
        try:
            g = plain(gw, 'address')
        except ValueError:
            raise Refused('the gateway is one IPv4 address')
        # Going back (1.0.262): the gateway the machine had, outside the subnet too (an on-link
        # route) - refused, the network of a trial not kept stayed.
        if g.version != 4 or (g not in a4.network and not r.get('rollback')):
            raise Refused('the gateway %s is not in %s' % (g, a4.network))
        out['gw4'] = str(g)
    else:
        out['gw4'] = ''
    dns = []
    for d in (v4.get('dns') or [])[:4] + ((r.get('ipv6') or {}).get('dns') or [])[:4]:
        try:
            dns.append(str(plain(d, 'address')))
        except ValueError:
            raise Refused('%r is not the address of a DNS server' % str(d)[:60])
    out['dns4'] = [d for d in dns if ':' not in d]
    out['dns6'] = [d for d in dns if ':' in d]
    search = []
    for s_ in (v4.get('search') or [])[:6]:
        if not NAME_RE.match(str(s_)):
            raise Refused('%r is not a domain' % str(s_)[:60])
        search.append(str(s_))
    out['search'] = search
    v6 = r.get('ipv6') or {}
    mode = str(v6.get('mode') or 'off')
    if mode not in ('off', 'auto', 'manual', 'keep'):
        raise Refused('IPv6 is off, auto, manual or keep')
    out['mode6'] = mode
    if mode == 'manual':
        try:
            a6 = plain(v6.get('addr'), 'interface')
        except ValueError:
            raise Refused('the IPv6 address is an address with its prefix (2001:db8::10/64)')
        if a6.version != 6 or a6.ip.is_link_local or '/' not in str(v6.get('addr')):
            raise Refused('the IPv6 address is a global one with its prefix (2001:db8::10/64)')
        out['addr6'] = str(a6)
        g6 = str(v6.get('gw') or '').strip()
        if g6:
            try:
                gg = plain(g6, 'address')
            except ValueError:
                raise Refused('the IPv6 gateway is one IPv6 address')
            if gg.version != 6:
                raise Refused('the IPv6 gateway is one IPv6 address')
            out['gw6'] = str(gg)
        else:
            out['gw6'] = ''
    host = str(r.get('hostname') or '').strip().rstrip('.').lower()
    # Going back may ask for a short name again - the one the machine had. So may a change
    # that keeps the name the machine has now (1.0.261): the daemon lets a short name as it is
    # through (net_check, 1.0.139), and root refused it here - a machine named "otp1" could not
    # be given a new address from the pages at all, and the other node had been told it.
    if host and (not NAME_RE.match(host) or ('.' not in host and not r.get('rollback') and
                                             host != net_static_hostname())):
        raise Refused('the host name is the whole name: otp1.example.cz')
    out['hostname'] = host
    snap = str(r.get('snapshot') or '')
    out['snapshot'] = snap if re.match(r'^[0-9a-f]{8,40}\Z', snap) else ''
    olds = []
    for o in (r.get('old') or [])[:8]:
        try:
            olds.append(str(plain(o, 'address')))
        except ValueError:
            pass
    out['old'] = olds
    old_host = str(r.get('old_hostname') or '').strip().lower()
    out['old_hostname'] = old_host if NAME_RE.match(old_host or 'x') else ''
    try:
        out['reboot_in'] = max(0, min(600, int(r.get('reboot_in') or 0)))
    except (TypeError, ValueError):
        out['reboot_in'] = 0
    return out


def net_static_hostname():
    """The machine's static host name as it is now, lower case ('' unknown) (1.0.261) - the
    kernel's when hostnamectl says none or fails (1.0.262), as net_read() tells the daemon."""
    try:
        got = run([HOSTNAMECTL, '--static'], 'hostnamectl').strip()
    except (Refused, OSError):
        got = ''
    if not got:
        try:
            got = os.uname().nodename
        except OSError:
            got = ''
    return str(got or '').strip().rstrip('.').lower()


def hosts_lines(text, n):
    """/etc/hosts with this machine's lines for its old addresses and names
    taken out and its new ones put in; localhost lines kept as they are."""
    short = n['hostname'].split('.')[0] if n['hostname'] else ''
    drop_names = set(x for x in (n['hostname'], short, n['old_hostname'],
                                 n['old_hostname'].split('.')[0]) if x)
    out = []
    for line in text.splitlines():
        f = line.split('#', 1)[0].split()
        if f and not f[0].startswith(('127.', '::1')):
            if f[0] in n['old'] or f[0] == n['addr4'].split('/')[0] or \
                    any(x.lower() in drop_names for x in f[1:]):
                continue
        out.append(line)
    if n['hostname']:
        out.append('%s %s %s    # this machine - written by otp' % (
            n['addr4'].split('/')[0], n['hostname'], short))
        if n.get('addr6'):
            out.append('%s %s %s    # this machine - written by otp' % (
                n['addr6'].split('/')[0], n['hostname'], short))
    return '\n'.join(out) + '\n'


def power_after(what, secs):
    """A reboot or a power-off a few seconds from now - after this helper
    has written its answer and the page has had it."""
    secs = max(3, int(secs or 5))
    if POWER_CMD:
        with open(POWER_CMD, 'a') as f:
            f.write('%s %d %s\n' % (what, secs, time.time()))
        return '%s in %d s (written to %s)' % (what, secs, POWER_CMD)
    if NO_SERVICES:
        return '%s in %d s (not here: tests)' % (what, secs)
    run(['systemd-run', '--on-active=%ds' % secs, '--unit',
         'otp-%s-%d' % (what, int(time.time())), '/usr/bin/systemctl', what],
        'systemd-run %s' % what)
    return '%s in %d s' % (what, secs)


def net_addrs4_after(before, addr4):
    """The IPv4 addresses the connection gets (1.0.262): the first one (the address changed)
    replaced by the new one, the others set by hand before kept - all of them were replaced,
    and a second address (replication, a service of its own) went away with the change."""
    out = [addr4]
    if str(before.get('ipv4.method') or '') != 'manual':
        return out
    new_ip = addr4.split('/')[0]
    for a in nm_list(before.get('ipv4.addresses'))[1:8]:
        if a.split('/')[0] != new_ip and a not in out:
            out.append(a)
    return out


def net_apply(n):
    if not shutil.which(NMCLI):
        raise Refused('NetworkManager (nmcli) is not on this machine: set the network by hand')
    cons = [l.replace('\\:', ':') for l in run([NMCLI, '-t', '-g', 'NAME', 'connection',
                                                'show'], 'nmcli connection show').splitlines()]
    if n['con'] not in cons:
        raise Refused('there is no connection %r here' % n['con'])
    said = []
    before = nm_fields(n['con'], ['ipv4.method', 'ipv4.addresses', 'ipv4.gateway', 'ipv4.dns',
                                  'ipv4.dns-search', 'ipv6.method', 'ipv6.addresses',
                                  'ipv6.gateway', 'ipv6.dns'])
    # The old addresses and name taken out of /etc/hosts only as this machine has
    # them now (1.0.209): taken as the request said, any line of it - the
    # directory's, the repository's - could be taken away.
    have = set()
    for key in ('ipv4.addresses', 'ipv6.addresses'):
        for a in nm_list(before.get(key)):
            have.add(a.split('/')[0])
    n['old'] = [o for o in n['old'] if o in have]
    try:
        host_was = run([HOSTNAMECTL, '--static'], 'hostnamectl').strip().lower()
    except Exception:                                   # noqa: BLE001
        host_was = ''
    if n['old_hostname'] and n['old_hostname'] not in (host_was, host_was.split('.')[0]):
        n['old_hostname'] = ''
    if n.get('snapshot'):
        said.append(net_snapshot(n['con'], n['snapshot']))
    args = [NMCLI, 'connection', 'modify', n['con'],
            'ipv4.method', 'manual', 'ipv4.addresses', ','.join(net_addrs4_after(before, n['addr4'])),
            'ipv4.gateway', n['gw4'], 'ipv4.dns', ','.join(n['dns4']),
            'ipv4.dns-search', ','.join(n['search']), 'ipv4.ignore-auto-dns', 'yes']
    if n['mode6'] == 'off':
        args += ['ipv6.method', 'disabled', 'ipv6.addresses', '', 'ipv6.gateway', '',
                 'ipv6.dns', '']
    elif n['mode6'] == 'auto':
        args += ['ipv6.method', 'auto', 'ipv6.addresses', '', 'ipv6.gateway', '',
                 'ipv6.dns', ','.join(n['dns6'])]
    elif n['mode6'] == 'manual':
        args += ['ipv6.method', 'manual', 'ipv6.addresses', n['addr6'],
                 'ipv6.gateway', n['gw6'], 'ipv6.dns', ','.join(n['dns6'])]
    run(args, 'nmcli connection modify')
    said.append('NetworkManager: %s - %s via %s, DNS %s%s' % (
        n['con'], n['addr4'], n['gw4'] or 'no gateway', ', '.join(n['dns4']) or 'none',
        {'off': ', IPv6 off', 'auto': ', IPv6 automatic',
         'manual': ', IPv6 %s' % n.get('addr6'), 'keep': ''}[n['mode6']]))
    if n['mode6'] in ('auto', 'manual'):
        # IPv6 switched off in the kernel by an earlier hand: on again.
        f6 = NET_SYSCTL6
        write_root(f6, '%s\nnet.ipv6.conf.all.disable_ipv6 = 0\nnet.ipv6.conf.default.'
                   'disable_ipv6 = 0\n' % MARK, 0o644)
    if n['hostname']:
        run([HOSTNAMECTL, 'set-hostname', n['hostname']], 'hostnamectl set-hostname')
        said.append('host name: %s' % n['hostname'])
    try:
        with open(HOSTS_FILE) as f:
            had = f.read()
    except OSError:
        had = '127.0.0.1 localhost localhost.localdomain\n::1 localhost localhost.localdomain\n'
    new = hosts_lines(had, n)
    if new != had:
        try:
            write_root(HOSTS_FILE + '.otp-before', had, 0o644)
        except OSError:
            pass
        write_root(HOSTS_FILE, new, 0o644)
        said.append('%s: this machine\'s lines' % HOSTS_FILE)
    if n['reboot_in']:
        said.append(power_after('reboot', n['reboot_in']))
    return {'said': said, 'before': before}


def _read_or_none(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


def nm_props(con):
    """Every ipv4.* and ipv6.* property of the connection, as nmcli shows it."""
    out = {}
    for line in run([NMCLI, '-t', '-f', 'ipv4,ipv6', 'connection', 'show', con],
                    'nmcli connection show').splitlines():
        k, sep, v = line.partition(':')
        if sep and re.match(r'^ipv[46]\.[a-z0-9-]+\Z', k):
            out[k] = v.replace('\\:', ':')
    return out


def net_snapshot(con, snap_id):
    """Everything of the machine's network a change touches, kept as it is now
    (1.0.139): the connection's profile whole - every address, route, MTU,
    DHCP or not - its ipv4/ipv6 properties, the host name, /etc/hosts and
    the IPv6 switch. Going back puts exactly this back."""
    profile_path, profile = '', None
    try:
        got = run([NMCLI, '-t', '-g', 'GENERAL.FILENAME', 'connection', 'show', con],
                  'nmcli connection show').strip()
        if got.startswith(NET_PROFILE_DIRS) and '/../' not in got:
            profile_path, profile = got, _read_or_none(got)
    except Refused:
        pass
    try:
        host = run([HOSTNAMECTL, '--static'], 'hostnamectl').strip()
    except (Refused, OSError):
        host = ''
    snap = {'id': snap_id, 'at': time.time(), 'con': con, 'profile_path': profile_path,
            'profile': profile, 'props': nm_props(con), 'hostname': host,
            'hosts': _read_or_none(HOSTS_FILE), 'sysctl6': _read_or_none(NET_SYSCTL6)}
    os.makedirs(NET_SNAP_DIR, mode=0o700, exist_ok=True)
    os.chmod(NET_SNAP_DIR, 0o700)
    write_root(os.path.join(NET_SNAP_DIR, NET_SNAP_FILE), json.dumps(snap), 0o600)
    return 'what the machine has now kept, to go back to: %s' % (
        'the whole profile of %s' % con if profile is not None
        else 'the IPv4 and IPv6 settings of %s' % con)


def net_restore(r):
    """The network as it was before the change on trial: the profile put back
    whole, the host name, /etc/hosts and the IPv6 switch - then a reboot."""
    snap_id = str(r.get('snapshot') or '')
    try:
        with open(os.path.join(NET_SNAP_DIR, NET_SNAP_FILE)) as f:
            snap = json.load(f)
    except (OSError, ValueError):
        raise Refused('nothing kept to go back to on this machine')
    if not isinstance(snap, dict) or not snap_id or snap.get('id') != snap_id:
        raise Refused('what is kept here is of another change (%s)' % str(
            (snap or {}).get('id') if isinstance(snap, dict) else '?')[:20])
    con = str(snap.get('con') or '')
    said = []
    path, profile = str(snap.get('profile_path') or ''), snap.get('profile')
    done = False
    if profile is not None and path.startswith(NET_PROFILE_DIRS) and '/../' not in path:
        st = None
        try:
            st = os.stat(path)
        except OSError:
            pass
        write_root(path, profile, stat.S_IMODE(st.st_mode) if st else 0o600)
        try:
            run([NMCLI, 'connection', 'load', path], 'nmcli connection load')
            # A profile of /run (1.0.248): the change made it one of /etc, which the reboot
            # keeps while /run is emptied - its settings put back one by one as well.
            done = not path.startswith('/run/')
            said.append('NetworkManager: the profile of %s put back as it was' % con)
        except Refused as e:
            said.append('the profile could not be loaded (%s) - its settings put back one by '
                        'one' % e)
    if not done:
        props = snap.get('props') or {}
        args = [NMCLI, 'connection', 'modify', con]
        for k in sorted(props):
            v = props[k]
            args += [k, '' if v in ('--', None) else v]
        try:
            run(args, 'nmcli connection modify')
            said.append('NetworkManager: every IPv4 and IPv6 setting of %s put back' % con)
        except Refused:
            keys = ('ipv4.method', 'ipv4.addresses', 'ipv4.gateway', 'ipv4.dns',
                    'ipv4.dns-search', 'ipv4.routes', 'ipv4.ignore-auto-dns', 'ipv6.method',
                    'ipv6.addresses', 'ipv6.gateway', 'ipv6.dns', 'ipv6.routes')
            args = [NMCLI, 'connection', 'modify', con]
            for k in keys:
                if k in props:
                    args += [k, '' if props[k] in ('--', None) else props[k]]
            run(args, 'nmcli connection modify')
            said.append('NetworkManager: the addresses, routes and DNS of %s put back' % con)
    host = str(snap.get('hostname') or '')
    if host and NAME_RE.match(host):
        run([HOSTNAMECTL, 'set-hostname', host], 'hostnamectl set-hostname')
        said.append('host name: %s' % host)
    if snap.get('hosts') is not None:
        write_root(HOSTS_FILE, snap['hosts'], 0o644)
        said.append('%s as it was' % HOSTS_FILE)
    if snap.get('sysctl6') is None:
        if os.path.exists(NET_SYSCTL6):
            os.unlink(NET_SYSCTL6)
    else:
        write_root(NET_SYSCTL6, snap['sysctl6'], 0o644)
    try:
        reboot_in = max(0, min(600, int(r.get('reboot_in') or 0)))
    except (TypeError, ValueError):
        reboot_in = 0
    if reboot_in:
        said.append(power_after('reboot', reboot_in))
    return {'said': said}


def net_part():
    d = web_fd()
    try:
        raw = read_req(NET_ASK, 65536)
    except FileNotFoundError:
        return
    except (Refused, OSError):
        drop_ask(NET_ASK, d)
        return
    drop_ask(NET_ASK, d)
    out = {'at': time.time(), 'ok': False, 'id': ''}
    try:
        r = json.loads(raw.decode('utf-8'))
        if not isinstance(r, dict):
            raise Refused('the request is not an object')
        out['id'] = re.sub(r'[^A-Za-z0-9]', '', str(r.get('id') or ''))[:40]
        what = r.get('do')
        if what == 'read':
            out['data'] = net_read()
        elif what == 'apply':
            out['data'] = net_apply(net_checked(r))
        elif what == 'restore':
            out['data'] = net_restore(r)
        elif what == 'power':
            how = r.get('how')
            if how not in ('reboot', 'poweroff'):
                raise Refused('reboot or poweroff')
            try:
                secs = int(r.get('in') or 5)
            except (TypeError, ValueError):
                secs = 5
            out['data'] = {'said': [power_after(how, secs)]}
        else:
            raise Refused('read, apply, restore or power')
        out['ok'] = True
    except Refused as e:
        out['said'] = str(e)[:400]
    except Exception as e:                              # noqa: BLE001
        out['said'] = 'it went wrong: %s' % str(e)[:300]
    write_here(NET_FILE, json.dumps(out))


# ---- the time: chrony (1.0.120) ---------------------------------------------------
# Asked in ntp.ask: how the clock is (read), chrony's servers set (apply), a
# step to the right time now (sync). /etc/chrony.conf keeps everything of its
# own; when otp sets the servers, the file's own server/pool/makestep/allow
# lines are commented out (#otp#) and otp's block is added between marks -
# put back as they were when otp stops setting them.
NTP_ASK = 'ntp.ask'
NTP_FILE = 'ntp.json'
CHRONYC = os.environ.get('OTP_CHRONYC', 'chronyc')
TIMEDATECTL = os.environ.get('OTP_TIMEDATECTL', 'timedatectl')
# Debian and Ubuntu read /etc/chrony/chrony.conf (1.0.146): the other was
# written there and never read, and "applied" said so.
CHRONY_CONF = os.environ.get('OTP_CHRONY_CONF') or next(
    (p for p in ('/etc/chrony.conf', '/etc/chrony/chrony.conf') if os.path.isfile(p)),
    '/etc/chrony.conf')
NTP_BEGIN = '# ---- otp: the time servers, set on its pages (Settings - Time) ----'
NTP_END = '# ---- otp: end ----'
NTP_KEYS = ('server', 'pool', 'peer', 'makestep', 'allow', 'minsources', 'maxdistance', 'sourcedir')
TZ_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_+-]{0,39}(/[A-Za-z0-9_+-]{1,40}){0,3}\Z')   # no -option (1.0.234)


def ntp_read():
    out = {'chrony': bool(shutil.which(CHRONYC)), 'tracking': {}, 'sources': [], 'stats': {}}
    try:
        t = run([TIMEDATECTL, 'show'], 'timedatectl', ok=(0, 1))
        for line in t.splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                if k in ('Timezone', 'NTP', 'NTPSynchronized', 'LocalRTC', 'CanNTP'):
                    out[k.lower()] = v
    except (Refused, OSError):
        pass
    out['time'] = time.time()
    if not out['chrony']:
        return out
    try:
        f = run([CHRONYC, '-c', 'tracking'], 'chronyc tracking').strip().split(',')
        if len(f) >= 14:
            out['tracking'] = {'ref_id': f[0], 'ref': f[1], 'stratum': int(f[2] or 0),
                               'ref_time': float(f[3] or 0), 'offset': float(f[4] or 0),
                               'last_offset': float(f[5] or 0), 'rms': float(f[6] or 0),
                               'freq': float(f[7] or 0), 'skew': float(f[9] or 0),
                               'root_delay': float(f[10] or 0), 'root_disp': float(f[11] or 0),
                               'interval': float(f[12] or 0), 'leap': f[13]}
    except (Refused, ValueError, OSError) as e:
        out['said'] = str(e)[:200]
    try:
        for line in run([CHRONYC, '-c', 'sources'], 'chronyc sources').splitlines():
            f = line.split(',')
            if len(f) < 10:
                continue
            try:
                out['sources'].append({'mode': f[0], 'state': f[1], 'name': f[2][:120],
                                       'stratum': int(f[3] or 0), 'poll': int(f[4] or 0),
                                       'reach': int(f[5] or 0, 8) if f[5] else 0,
                                       'last_rx': int(f[6]) if f[6].lstrip('-').isdigit() else None,
                                       'offset': float(f[7] or 0), 'measured': float(f[8] or 0),
                                       'error': float(f[9] or 0)})
            except ValueError:
                continue
    except (Refused, OSError):
        pass
    try:
        with open(CHRONY_CONF) as f:
            text = f.read()
        out['managed'] = NTP_BEGIN in text
        out['own'] = [l.strip() for l in text.splitlines()
                      if (l.split() or [''])[0] in ('server', 'pool', 'peer')][:20]
    except OSError:
        out['managed'] = False
    return out


def ntp_checked(r):
    out = {'manage': bool(r.get('manage')), 'servers': [], 'allow': [],
           'makestep': [1.0, 3], 'minsources': 1, 'timezone': '', 'peers': []}
    for x in (r.get('servers') or [])[:12]:
        if not isinstance(x, dict):
            raise Refused('a server is an object')
        host = str(x.get('host') or '').strip().lower().rstrip('.')
        try:
            host = str(plain(host, 'address'))
        except ValueError:
            if not NAME_RE.match(host):
                raise Refused('%r is not a host name or an address' % host[:80])
        out['servers'].append({'host': host, 'pool': bool(x.get('pool')),
                               'iburst': bool(x.get('iburst', True)),
                               'prefer': bool(x.get('prefer')), 'nts': bool(x.get('nts'))})
    for p in (r.get('peers') or [])[:2]:
        try:
            out['peers'].append(str(plain(p, 'address')))
        except ValueError:
            raise Refused('%r is not the other node\'s address' % str(p)[:60])
    for a in (r.get('allow') or [])[:20]:
        try:
            out['allow'].append(str(plain(a, 'network')))
        except ValueError:
            raise Refused('%r is not a network (192.0.2.0/24)' % str(a)[:60])
    try:
        th = float((r.get('makestep') or [1.0, 3])[0])
        lim = int((r.get('makestep') or [1.0, 3])[1])
    except (TypeError, ValueError, IndexError):
        raise Refused('makestep is a threshold in seconds and a number of updates')
    if not (0.001 <= th <= 3600) or not (-1 <= lim <= 1000):
        raise Refused('makestep: 0.001 - 3600 s, and -1 (always) to 1000 updates')
    out['makestep'] = [th, lim]
    try:
        out['minsources'] = max(1, min(10, int(r.get('minsources') or 1)))
    except (TypeError, ValueError):
        out['minsources'] = 1
    tz = str(r.get('timezone') or '').strip()
    if tz and not TZ_RE.match(tz):
        raise Refused('%r is not a time zone' % tz[:60])
    out['timezone'] = tz
    if out['manage'] and not out['servers'] and not out['peers']:
        raise Refused('at least one time server')
    return out


def ntp_conf_text(text, n):
    """chrony.conf with otp's block (or without it, put back as it was)."""
    lines = text.splitlines()
    out, inside = [], False
    for l in lines:
        if l.strip() == NTP_BEGIN:
            inside = True
            continue
        if l.strip() == NTP_END:
            inside = False
            continue
        if inside:
            continue
        if l.startswith('#otp# '):
            l = l[6:]                       # the file's own line, put back first
        out.append(l)
    if not n['manage']:
        return '\n'.join(out).rstrip('\n') + '\n'
    kept = []
    for l in out:
        # Any whitespace (1.0.255): chrony takes "server<TAB>host" too, and such a line was
        # left in beside otp's block - two sets of sources.
        if (l.split() or [''])[0] in NTP_KEYS:
            kept.append('#otp# ' + l)
        else:
            kept.append(l)
    block = [NTP_BEGIN]
    for x in n['servers']:
        opts = [o for o, on in (('iburst', x['iburst']), ('prefer', x['prefer']),
                                ('nts', x['nts'])) if on]
        block.append('%s %s %s' % ('pool' if x['pool'] else 'server', x['host'], ' '.join(opts)))
    for p in n['peers']:
        # The other node of the cluster: one more source, and allowed to ask.
        block.append('server %s iburst' % p)
        block.append('allow %s' % p)
    for a in n['allow']:
        block.append('allow %s' % a)
    block.append('makestep %s %d' % (('%g' % n['makestep'][0]), n['makestep'][1]))
    if n['minsources'] > 1:
        block.append('minsources %d' % n['minsources'])
    block.append(NTP_END)
    return '\n'.join([l.rstrip() for l in kept]).rstrip('\n') + '\n\n' + '\n'.join(block) + '\n'


def ntp_apply(n):
    said = []
    if not shutil.which(CHRONYC) and not NO_SERVICES:
        if shutil.which('dnf'):
            run(['dnf', '-y', 'install', 'chrony'], 'dnf install chrony')
            said.append('chrony installed')
        else:
            raise Refused('chrony is not on this machine')
    try:
        with open(CHRONY_CONF) as f:
            had = f.read()
    except FileNotFoundError:
        had = 'driftfile /var/lib/chrony/drift\nrtcsync\nlogdir /var/log/chrony\n'
    new = ntp_conf_text(had, n)
    if new != had:
        if NTP_BEGIN not in had:
            try:
                write_root(CHRONY_CONF + '.otp-before', had, 0o644)
            except OSError:
                pass
        write_root(CHRONY_CONF, new, 0o644)
        said.append('%s: %s' % (CHRONY_CONF, ', '.join(x['host'] for x in n['servers'])
                                if n['manage'] else 'its own servers again'))
        if not NO_SERVICES and not os.environ.get('OTP_NTP_NO_SERVICE'):
            try:
                run(['systemctl', 'enable', '--now', 'chronyd'], 'systemctl enable chronyd')
                run(['systemctl', 'restart', 'chronyd'], 'systemctl restart chronyd')
            except Refused as e:
                # chronyd will not start on the new file (an older chrony and "nts", say -
                # 1.0.248): the file as it was, and chronyd started on it again.
                write_root(CHRONY_CONF, had, 0o644)
                try:
                    run(['systemctl', 'restart', 'chronyd'], 'systemctl restart chronyd')
                except Refused:
                    pass
                raise Refused('%s - chrony.conf put back as it was' % e)
            said.append('chronyd restarted')
    if n['timezone']:
        try:
            cur = run([TIMEDATECTL, 'show', '-p', 'Timezone', '--value'], 'timedatectl').strip()
        except Refused:
            cur = ''
        if cur != n['timezone']:
            run([TIMEDATECTL, 'set-timezone', n['timezone']], 'timedatectl set-timezone')
            said.append('time zone: %s' % n['timezone'])
    if not NO_SERVICES and shutil.which(TIMEDATECTL) and not os.environ.get('OTP_NTP_NO_SERVICE'):
        run([TIMEDATECTL, 'set-ntp', 'true'], 'timedatectl set-ntp', ok=(0, 1))
    return {'said': said}


def ntp_part():
    d = web_fd()
    try:
        raw = read_req(NTP_ASK, 65536)
    except FileNotFoundError:
        return
    except (Refused, OSError):
        drop_ask(NTP_ASK, d)
        return
    drop_ask(NTP_ASK, d)
    out = {'at': time.time(), 'ok': False, 'id': ''}
    try:
        r = json.loads(raw.decode('utf-8'))
        if not isinstance(r, dict):
            raise Refused('the request is not an object')
        out['id'] = re.sub(r'[^A-Za-z0-9]', '', str(r.get('id') or ''))[:40]
        what = r.get('do')
        if what == 'read':
            out['data'] = ntp_read()
            if r.get('zones'):
                try:
                    out['data']['zones'] = run([TIMEDATECTL, 'list-timezones'],
                                               'timedatectl').split()[:700]
                except Refused:
                    pass
        elif what == 'apply':
            out['data'] = ntp_apply(ntp_checked(r))
        elif what == 'sync':
            said = run([CHRONYC, 'makestep'], 'chronyc makestep').strip()
            run([CHRONYC, 'burst', '4/4'], 'chronyc burst', ok=(0, 1))
            out['data'] = {'said': [said or 'stepped']}
        else:
            raise Refused('read, apply or sync')
        out['ok'] = True
    except Refused as e:
        out['said'] = str(e)[:400]
    except Exception as e:                              # noqa: BLE001
        out['said'] = 'it went wrong: %s' % str(e)[:300]
    write_here(NTP_FILE, json.dumps(out))


def status_read():
    """What this helper wrote last. It lies in the folder the otp account
    owns, so nothing of it is trusted (1.0.57): what is used again - the
    peer, its family, the interface, the DH choices - is checked again."""
    try:
        got = json.loads(read_req('status.json').decode('utf-8'))
    except (OSError, ValueError, Refused):
        return {}
    if not isinstance(got, dict):
        return {}
    a = got.get('applied') if isinstance(got.get('applied'), dict) else {}
    keep = {}
    try:
        if a.get('peer'):
            keep['peer'] = str(plain(a['peer'], 'address'))
            keep['family'] = 6 if ':' in keep['peer'] else 4
        if a.get('iface') and IFACE_RE.match(str(a['iface'])):
            keep['iface'] = str(a['iface'])
    except ValueError:
        keep = {}
    got['applied'] = keep
    dh = got.get('dh') if isinstance(got.get('dh'), dict) else {}
    got['dh'] = {k: v for k, v in dh.items() if k in ('node', 'vip') and v in DH_CHOICES}
    return got


# ---- the otp console when root signs in (1.0.141) ---------------------------------
# Asked in console.ask from the pages (Settings - About): on or off, written to
# /etc/otp-console-login as `otp --console-at-login` writes it.
CONSOLE_ASK = 'console.ask'
CONSOLE_FILE = 'console.json'
CONSOLE_FLAG = os.environ.get('OTP_CONSOLE_FLAG', '/etc/otp-console-login')


USER_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_.-]{0,31}\Z')


def console_flag_read():
    """(root on, the normal users it opens for: '*', a list, or []) - from the file itself, never
    through a link. The second line (1.0.240): 'users: *' or 'users: alice bob'."""
    try:
        fd = os.open(CONSOLE_FLAG, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return False, []
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return False, []
        text = os.read(fd, 8192).decode('utf-8', 'replace')
    finally:
        os.close(fd)
    lines = text.split('\n')
    users = []
    for ln in lines[1:]:
        if ln.startswith('users:'):
            words = ln[6:].split()
            users = '*' if words == ['*'] else [w for w in words if USER_NAME_RE.match(w)][:200]
    return lines[0].strip() == 'on', users


def console_users_checked(users):
    if users is None or users == '*':
        return users
    if not isinstance(users, list) or len(users) > 200:
        raise Refused('the users: "*" or a list of names, 200 at most')
    out = []
    for u in users:
        if not isinstance(u, str) or not USER_NAME_RE.match(u) or u == 'root':
            raise Refused('%r is not the name of a normal user' % str(u)[:40])
        if u not in out:
            out.append(u)
    return out


def console_flag_set(on, users=None):
    """Written beside it and put in its place: a link or a pipe found there is
    replaced, never followed. `users` None: as they were (1.0.240)."""
    if users is None:
        users = console_flag_read()[1]
    text = ('on\n' if on else 'off\n')
    if users:
        text += 'users: %s\n' % ('*' if users == '*' else ' '.join(users))
    tmp = '%s.%d.tmp' % (CONSOLE_FLAG, os.getpid())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        os.write(fd, text.encode())
        os.fchmod(fd, 0o644)
    finally:
        os.close(fd)
    os.rename(tmp, CONSOLE_FLAG)


def console_part():
    d = web_fd()
    try:
        raw = read_req(CONSOLE_ASK, 4096)
    except FileNotFoundError:
        return
    except (Refused, OSError):
        drop_ask(CONSOLE_ASK, d)
        return
    drop_ask(CONSOLE_ASK, d)
    out = {'at': time.time(), 'ok': False, 'id': ''}
    try:
        r = json.loads(raw.decode('utf-8'))
        if not isinstance(r, dict):
            raise Refused('the request is not an object')
        out['id'] = re.sub(r'[^A-Za-z0-9]', '', str(r.get('id') or ''))[:40]
        if r.get('do') != 'set' or not isinstance(r.get('on'), bool):
            raise Refused('set, on or off')
        console_flag_set(r['on'], console_users_checked(r.get('users')))
        on, users = console_flag_read()
        out['data'] = {'on': on, 'users': users}
        out['ok'] = True
    except Refused as e:
        out['said'] = str(e)[:400]
    except Exception as e:                              # noqa: BLE001
        out['said'] = 'it went wrong: %s' % str(e)[:300]
    write_here(CONSOLE_FILE, json.dumps(out))


# ---- the SSH keys root signs in with (1.0.158) ---------------------------------------
SSHKEYS_ASK = 'sshkeys.ask'
SSHKEYS_FILE = 'sshkeys.json'
ROOT_AUTH = os.environ.get('OTP_ROOT_AUTHKEYS', '/root/.ssh/authorized_keys')
KEY_TYPES = ('ssh-ed25519', 'ecdsa-sha2-nistp256', 'ecdsa-sha2-nistp384', 'ecdsa-sha2-nistp521',
             'ssh-rsa', 'sk-ssh-ed25519@openssh.com', 'sk-ecdsa-sha2-nistp256@openssh.com')
KEY_LINE_RE = re.compile(r'^(?P<type>[a-z0-9@.-]+) (?P<blob>[A-Za-z0-9+/]{40,16000}={0,3})'
                         r'(?: (?P<comment>[^\x00-\x1f\x7f]{0,200}))?\Z')


def key_facts(line):
    """(bits, SHA256:..., type) of one public key line, read by ssh-keygen."""
    got = subprocess.run(['ssh-keygen', '-l', '-E', 'sha256', '-f', '-'], input=line + '\n',
                         capture_output=True, text=True, timeout=20)
    # ED25519-SK, ECDSA-SK too (1.0.252): \w took no '-', and a security key was never read -
    # refused when added, never dropped, not counted as root's key.
    m = re.match(r'^(\d+) (SHA256:[A-Za-z0-9+/=]+) .*\(([\w-]+)\)\s*$', got.stdout.strip())
    if got.returncode != 0 or not m:
        return None
    return int(m.group(1)), m.group(2), m.group(3)


def auth_lines():
    """The lines of root's authorized_keys - none where it is not there. Never
    through a link."""
    try:
        fd = os.open(ROOT_AUTH, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return []
    except OSError as e:
        raise Refused('%s cannot be read: %s' % (ROOT_AUTH, e))
    with os.fdopen(fd, 'r', encoding='utf-8', errors='replace') as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise Refused('%s is not a plain file' % ROOT_AUTH)
        return f.read(AUTH_READ_MAX).split('\n')


AUTH_KEYS_MAX = 1000
# What of an authorized_keys is read (1.0.255): a file longer than that is not written again
# from what was read of it - its end, keys among it, was cut off without a word.
AUTH_READ_MAX = 1 << 20


def auth_too_long(path, size):
    if size > AUTH_READ_MAX:
        raise Refused('%s is longer than the %d MiB read of it - it is not written again from a '
                      'part: shorten it by hand first' % (path, AUTH_READ_MAX >> 20))


def auth_keys(lines):
    # At most 1000 lines, and half a minute of ssh-keygen (1.0.248): a user's own file of many
    # thousand short lines kept the helper - and every other ask behind it - busy for half an hour.
    out = []
    end = time.monotonic() + 30
    for i, ln in enumerate(lines):
        t = ln.strip()
        if not t or t.startswith('#'):
            continue
        if len(out) >= AUTH_KEYS_MAX:
            break
        facts = key_facts(t) if time.monotonic() < end and len(t) <= 16500 else None
        m = KEY_LINE_RE.match(t)
        out.append({'line': i, 'fp': facts[1] if facts else '', 'bits': facts[0] if facts else 0,
                    'type': facts[2] if facts else '?',
                    'comment': (m.group('comment') or '') if m else '',
                    'options': not bool(m), 'readable': bool(facts),
                    # The line itself, for the page's export: public halves only.
                    'text': t[:16500]})
    return out


def auth_write(lines):
    """root's authorized_keys written whole: its folder made 0700 if it is not
    there, refused if it is a link; a new file of root's, 0600, renamed in."""
    folder = os.path.dirname(ROOT_AUTH)
    try:
        st = os.lstat(folder)
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            raise Refused('%s is not a plain folder' % folder)
    except FileNotFoundError:
        os.makedirs(folder, mode=0o700)
    try:
        st = os.lstat(ROOT_AUTH)
        if stat.S_ISLNK(st.st_mode):
            raise Refused('%s is a link - put the file itself there' % ROOT_AUTH)
        auth_too_long(ROOT_AUTH, st.st_size)
    except FileNotFoundError:
        pass
    text = '\n'.join(lines).rstrip('\n') + '\n'
    fd, tmp = tempfile.mkstemp(prefix='.authorized_keys.', dir=folder)
    try:
        os.fchmod(fd, 0o600)
        if os.geteuid() == 0:
            os.fchown(fd, 0, 0)
        with os.fdopen(fd, 'w') as f:
            fd = None
            f.write(text)
        os.replace(tmp, ROOT_AUTH)
    except BaseException:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    if shutil.which('restorecon') and not NO_SERVICES:
        subprocess.run(['restorecon', '-R', folder], capture_output=True)


def sshd_says():
    """What sshd makes of root and of keys: a key is no use where it does not
    let root in with one."""
    if not shutil.which('sshd'):
        return {'there': False}
    got = subprocess.run(['sshd', '-T'], capture_output=True, text=True, timeout=20)
    said = {}
    for ln in got.stdout.splitlines():
        k, _, v = ln.partition(' ')
        if k in ('permitrootlogin', 'pubkeyauthentication', 'passwordauthentication', 'port'):
            said[k] = v.strip()
    return {'there': True, 'permit_root': said.get('permitrootlogin', ''),
            'pubkey': said.get('pubkeyauthentication', ''),
            'password': said.get('passwordauthentication', ''), 'port': said.get('port', '')}


# ---- the SSH keys of the normal users (1.0.240) -----------------------------------------
# Every user of the machine who may sign in - UID_MIN..UID_MAX of /etc/login.defs, a shell
# that is not nologin or false - and their ~/.ssh/authorized_keys, read and written by a child
# that is that user (its own UID, groups and GID): a link or anything else they put in their own
# home can only ever touch what is theirs already.
LOGIN_DEFS = os.environ.get('OTP_LOGIN_DEFS', '/etc/login.defs')
NO_SHELLS = ('nologin', 'false', 'sync', 'shutdown', 'halt')
NOLOGIN_PATHS = ('/usr/sbin/nologin', '/sbin/nologin', '/bin/false', '/usr/bin/false')


def uid_range():
    lo, hi = 1000, 60000
    try:
        for ln in open(LOGIN_DEFS, encoding='utf-8', errors='replace'):
            w = ln.split()
            if len(w) >= 2 and w[0] in ('UID_MIN', 'UID_MAX') and w[1].isdigit():
                if w[0] == 'UID_MIN':
                    lo = int(w[1])
                else:
                    hi = int(w[1])
    except OSError:
        pass
    return lo, hi


def normal_users():
    """[{name, uid, home, shell}] of the users who may sign in here, by name - 500 at most."""
    import pwd
    lo, hi = uid_range()
    out = []
    for p in pwd.getpwall():
        if not lo <= p.pw_uid <= hi or p.pw_uid == 65534 or not USER_NAME_RE.match(p.pw_name):
            continue
        if not p.pw_shell or os.path.basename(p.pw_shell) in NO_SHELLS:
            continue
        if not p.pw_dir.startswith('/') or p.pw_dir == '/':
            continue
        out.append({'name': p.pw_name, 'uid': p.pw_uid, 'home': p.pw_dir, 'shell': p.pw_shell})
    out.sort(key=lambda x: x['name'])
    return out[:500]


def ssh_user(name):
    """The pwd entry of a normal user of normal_users() - refused for anybody else."""
    import pwd
    name = str(name or '')
    if not USER_NAME_RE.match(name) or not any(u['name'] == name for u in normal_users()):
        raise Refused('%s is not a user who may sign in on this machine' % name[:40])
    return pwd.getpwnam(name)


def as_user(pw, fn):
    """fn() run by a child that is the user - its answer (JSON) back through a pipe."""
    rd, wr = os.pipe()
    pid = os.fork()
    if pid == 0:
        code = 0
        try:
            os.close(rd)
            os.setgroups(os.getgrouplist(pw.pw_name, pw.pw_gid))
            os.setgid(pw.pw_gid)
            os.setuid(pw.pw_uid)
            if os.getuid() != pw.pw_uid or os.geteuid() != pw.pw_uid:
                raise OSError('could not become %s' % pw.pw_name)
            os.umask(0o077)
            try:
                got = {'ok': True, 'data': fn()}
            except Refused as e:
                got = {'ok': False, 'said': str(e)}
            except OSError as e:
                got = {'ok': False, 'said': '%s: %s' % (e.filename or pw.pw_name, e.strerror or e)}
            data = json.dumps(got).encode()[:4 << 20]
            while data:
                data = data[os.write(wr, data):]
        except BaseException as e:                      # noqa: BLE001
            try:
                os.write(wr, json.dumps({'ok': False, 'said': str(e)[:300]}).encode())
            except BaseException:                       # noqa: BLE001
                pass
            code = 1
        finally:
            os._exit(code)
    os.close(wr)
    chunks = []
    # A deadline (1.0.249): the child is the user's, who may stop it (SIGSTOP) - and every ask of
    # the helper waited behind it, half an hour at a time.
    end = time.time() + 30
    late = False
    with os.fdopen(rd, 'rb') as f:
        while True:
            left = end - time.time()
            ready = select.select([f], [], [], max(0.0, left))[0] if left > 0 else []
            if not ready:
                late = True
                break
            b = os.read(f.fileno(), 65536)
            if not b:
                break
            chunks.append(b)
    if late:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    os.waitpid(pid, 0)
    if late:
        raise Refused('the child working as %s did not answer in 30 s' % pw.pw_name)
    try:
        got = json.loads(b''.join(chunks).decode('utf-8', 'replace') or '{}')
    except ValueError:
        got = {}
    if not got.get('ok'):
        raise Refused(got.get('said') or 'it went wrong as %s' % pw.pw_name)
    return got.get('data')


def user_auth_paths(pw):
    return os.path.join(pw.pw_dir, '.ssh'), os.path.join(pw.pw_dir, '.ssh', 'authorized_keys')


def user_auth_read(pw):
    folder, path = user_auth_paths(pw)

    def go():
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            return ''
        except OSError as e:
            if e.errno == errno.ELOOP:
                raise Refused('%s is a link - put the file itself there' % path)
            raise
        with os.fdopen(fd, 'r', encoding='utf-8', errors='replace') as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                raise Refused('%s is not a plain file' % path)
            return f.read(AUTH_READ_MAX)
    return (as_user(pw, go) or '').split('\n')


def user_auth_write(pw, lines):
    """~/.ssh/authorized_keys of the user, written by the user: ~/.ssh made 0700 when it is not
    there, refused when it or the file is a link; a new file, 0600, renamed in."""
    folder, path = user_auth_paths(pw)
    text = '\n'.join(lines).rstrip('\n') + '\n'

    def go():
        hs = os.lstat(pw.pw_dir)
        if stat.S_ISLNK(hs.st_mode) or not stat.S_ISDIR(hs.st_mode) or hs.st_uid != pw.pw_uid:
            raise Refused('%s is not a home folder of %s\'s own' % (pw.pw_dir, pw.pw_name))
        try:
            st = os.lstat(folder)
            if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
                raise Refused('%s is not a plain folder' % folder)
        except FileNotFoundError:
            os.mkdir(folder, 0o700)
        try:
            st = os.lstat(path)
            if stat.S_ISLNK(st.st_mode):
                raise Refused('%s is a link - put the file itself there' % path)
            auth_too_long(path, st.st_size)
        except FileNotFoundError:
            pass
        fd, tmp = tempfile.mkstemp(prefix='.authorized_keys.', dir=folder)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, 'w') as f:
                fd = None
                f.write(text)
            os.replace(tmp, path)
        except BaseException:
            if fd is not None:
                os.close(fd)
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return True
    as_user(pw, go)
    if shutil.which('restorecon') and not NO_SERVICES:
        subprocess.run(['restorecon', '-R', folder], capture_output=True)


def key_line_checked(line):
    m = KEY_LINE_RE.match(line)
    if not m or m.group('type') not in KEY_TYPES:
        raise Refused('that is not one public key line (ssh-ed25519 AAAA... comment) - '
                      'options before the key are not taken here')
    facts = key_facts(line)
    if not facts:
        raise Refused('ssh-keygen does not read that key')
    bits, fp, kind = facts
    if kind == 'RSA' and bits < 3072:
        raise Refused('an RSA key of %d bits is too weak: 3072 at least, or ed25519' % bits)
    if kind == 'DSA':
        raise Refused('DSA keys are not taken')
    return fp


def sshkeys_user_do(r, name):
    """The same as for root, for a normal user - no "last key" guard: a user's password stays."""
    pw = ssh_user(name)
    do = r.get('do')
    lines = user_auth_read(pw)
    if do == 'add':
        line = str(r.get('line') or '').strip()
        fp = key_line_checked(line)
        if not any(k['fp'] == fp for k in auth_keys(lines)):
            user_auth_write(pw, [ln for ln in lines if ln.strip()] + [line])
    elif do == 'drop':
        fp = str(r.get('fp') or '')
        hit = [k for k in auth_keys(lines) if k['fp'] and k['fp'] == fp]
        if not hit:
            raise Refused('no key %s is there' % fp)
        gone = {k['line'] for k in hit}
        user_auth_write(pw, [ln for i, ln in enumerate(lines) if i not in gone])
    elif do != 'list':
        raise Refused('list, add or drop')
    lines = user_auth_read(pw)
    return {'user': name, 'keys': [dict((k, v) for k, v in x.items() if k != 'line')
                                   for x in auth_keys(lines)],
            'file': user_auth_paths(pw)[1], 'users': normal_users(), 'sshd': sshd_says()}


def sshkeys_do(r):
    user = str(r.get('user') or 'root')
    if user != 'root':
        return sshkeys_user_do(r, user)
    do = r.get('do')
    lines = auth_lines()
    if do == 'add':
        line = str(r.get('line') or '').strip()
        m = KEY_LINE_RE.match(line)
        if not m or m.group('type') not in KEY_TYPES:
            raise Refused('that is not one public key line (ssh-ed25519 AAAA... comment) - '
                          'options before the key are not taken here')
        facts = key_facts(line)
        if not facts:
            raise Refused('ssh-keygen does not read that key')
        bits, fp, kind = facts
        if kind == 'RSA' and bits < 3072:
            raise Refused('an RSA key of %d bits is too weak: 3072 at least, or ed25519' % bits)
        if kind == 'DSA':
            raise Refused('DSA keys are not taken')
        # There already is no fault: a key of root's the app was handed, or
        # one put on again (1.0.159).
        if not any(k['fp'] == fp for k in auth_keys(lines)):
            lines = [ln for ln in lines if ln.strip()] + [line]
            auth_write(lines)
    elif do == 'drop':
        fp = str(r.get('fp') or '')
        keys = auth_keys(lines)
        hit = [k for k in keys if k['fp'] and k['fp'] == fp]
        if not hit:
            raise Refused('no key %s is there' % fp)
        if len(keys) == len(hit) and not r.get('last_ok'):
            raise Refused('that is the last key root signs in with here - said again to take it '
                          'away anyway')
        gone = {k['line'] for k in hit}
        auth_write([ln for i, ln in enumerate(lines) if i not in gone])
    elif do != 'list':
        raise Refused('list, add or drop')
    lines = auth_lines()
    return {'keys': [dict((k, v) for k, v in x.items() if k != 'line') for x in auth_keys(lines)],
            'file': ROOT_AUTH, 'sshd': sshd_says(), 'user': 'root',
            # Who else may sign in here (1.0.240): their keys on the pages too.
            'users': normal_users()}


def sshkeys_part():
    d = web_fd()
    try:
        raw = read_req(SSHKEYS_ASK, 65536)
    except FileNotFoundError:
        return
    except (Refused, OSError):
        drop_ask(SSHKEYS_ASK, d)
        return
    drop_ask(SSHKEYS_ASK, d)
    out = {'at': time.time(), 'ok': False, 'id': ''}
    try:
        r = json.loads(raw.decode('utf-8'))
        if not isinstance(r, dict):
            raise Refused('the request is not an object')
        out['id'] = re.sub(r'[^A-Za-z0-9]', '', str(r.get('id') or ''))[:40]
        out['data'] = sshkeys_do(r)
        out['ok'] = True
    except Refused as e:
        out['said'] = str(e)[:400]
    except Exception as e:                              # noqa: BLE001
        out['said'] = 'it went wrong: %s' % str(e)[:300]
    write_here(SSHKEYS_FILE, json.dumps(out))


# ---- the local users of the machine (1.0.243) ----------------------------------------
# Made and looked after from Settings -> Local users, on every node of a cluster or on one:
# only the users of the range login.defs gives normal users (UID_MIN..UID_MAX) - never root,
# never an account of the system or of a service. root is read, never changed. A password
# comes as a hash only (made on the node it was typed on), handed to chpasswd -e on its
# standard input - never on a command line. Each change done is said back with the list.
USERS_ASK, USERS_FILE = 'users.ask', 'users.json'
SHADOW = os.environ.get('OTP_SHADOW', '/etc/shadow')
SHELLS_FILE = os.environ.get('OTP_SHELLS', '/etc/shells')
PW_HASH_RE = re.compile(r'^\$(?:6|5|y|gy|2b|2y)\$[./A-Za-z0-9$=]{16,300}\Z')
GECOS_RE = re.compile(r'^[^:\n\x00-\x1f\x7f]{0,120}\Z')
KEEP_NAMES = ('root', 'otp', 'otp-web', 'postgres', 'nginx', 'apache', 'nobody', 'keepalived',
              'chrony', 'sshd', 'polkitd', 'dbus', 'systemd-network', 'tss')


def lu_run(argv, data=None):
    """A tool of shadow-utils, its error said back - never with a secret among the words."""
    got = subprocess.run(argv, input=data, capture_output=True, text=True, timeout=120)
    if got.returncode != 0:
        msg = ((got.stderr or got.stdout or '').strip().splitlines() or ['exit %d' % got.returncode])[-1]
        raise Refused('%s: %s' % (os.path.basename(argv[0]), msg[:300]))
    return got.stdout


def lu_admin_group():
    """The group whose members may become root with sudo: wheel (RHEL) or sudo (Debian)."""
    import grp
    for g in ('wheel', 'sudo'):
        try:
            grp.getgrnam(g)
            return g
        except KeyError:
            continue
    return ''


def lu_shells():
    out = []
    try:
        for ln in open(SHELLS_FILE, encoding='utf-8', errors='replace'):
            ln = ln.strip()
            if ln.startswith('/') and not ln.startswith('#') and ' ' not in ln and ln not in out and \
                    os.path.basename(ln) not in NO_SHELLS:
                out.append(ln)
    except OSError:
        pass
    if not out and os.path.exists('/bin/bash'):
        out.append('/bin/bash')
    nl = '/usr/sbin/nologin' if os.path.exists('/usr/sbin/nologin') else '/sbin/nologin'
    return out[:20] + [nl]


def lu_shadow():
    """{name: (hash field, last change in days, max days, expire day)} - read as root."""
    out = {}
    try:
        with open(SHADOW, encoding='utf-8', errors='replace') as f:
            for ln in f:
                p = ln.rstrip('\n').split(':')
                if len(p) >= 8:
                    out[p[0]] = (p[1], p[2], p[4], p[7], p[3], p[5])
    except OSError:
        pass
    return out


def lu_one(p, sh, admin, today):
    import grp
    h, last, mx, exp, mn, wn = sh.get(p.pw_name, ('', '', '', '', '', ''))
    groups = sorted({g.gr_name for g in grp.getgrall() if p.pw_name in g.gr_mem} |
                    ({grp.getgrgid(p.pw_gid).gr_name} if _gid_ok(p.pw_gid) else set()))
    plain = h.lstrip('!')
    # Locked: a password put out of use (! before a real hash) or the account expired - a user
    # with no password at all ('!' or '!!' alone) is not, a key lets them in.
    locked = (h.startswith('!') and plain.startswith('$')) or (exp.isdigit() and int(exp) <= today)
    return {'name': p.pw_name, 'uid': p.pw_uid, 'gecos': p.pw_gecos.split(',')[0][:120],
            'home': p.pw_dir, 'shell': p.pw_shell,
            'login': bool(p.pw_shell) and os.path.basename(p.pw_shell) not in NO_SHELLS,
            'groups': groups[:40], 'sudo': bool(admin) and admin in groups,
            'password': bool(plain) and plain not in ('*', '!', 'x') and plain.startswith('$'),
            'locked': bool(locked), 'must_change': last == '0',
            'changed': int(last) if last.isdigit() and last != '0' else None,
            'expires': int(exp) if exp.isdigit() else None,
            'max_days': int(mx) if mx.isdigit() and int(mx) < 99999 else None,
            'min_days': int(mn) if mn.isdigit() else 0, 'warn_days': int(wn) if wn.isdigit() else None,
            # The day the password runs out (1.0.245): its last change and the days it is good.
            'pw_ends': (int(last) + int(mx)) if last.isdigit() and last != '0' and mx.isdigit()
            and int(mx) < 99999 else None,
            'home_there': os.path.isdir(p.pw_dir)}


def _gid_ok(gid):
    import grp
    try:
        grp.getgrgid(gid)
        return True
    except KeyError:
        return False


def lu_list():
    import pwd
    lo, hi = uid_range()
    sh, admin, today = lu_shadow(), lu_admin_group(), int(time.time() // 86400)
    users, used = [], []
    for p in pwd.getpwall():
        if lo <= p.pw_uid <= hi:
            used.append(p.pw_uid)
        if p.pw_name == 'root' or (lo <= p.pw_uid <= hi and p.pw_uid != 65534 and
                                   USER_NAME_RE.match(p.pw_name) and p.pw_name not in KEEP_NAMES):
            u = lu_one(p, sh, admin, today)
            u['root'] = p.pw_name == 'root'
            users.append(u)
    users.sort(key=lambda u: (not u['root'], u['name']))
    try:
        policy = pwp_read()
    except Exception as e:                              # noqa: BLE001
        policy = {'error': str(e)[:200]}
    return {'users': users[:500], 'uid_min': lo, 'uid_max': hi, 'used': sorted(set(used))[:5000],
            'policy': policy,
            'names': sorted(p.pw_name for p in pwd.getpwall())[:5000],
            'admin_group': admin, 'shells': lu_shells(), 'today': today}


def lu_target(name):
    """The pwd entry of a user this may change - refused for root, the system and services."""
    import pwd
    name = str(name or '')
    if not USER_NAME_RE.match(name) or name in KEEP_NAMES:
        raise Refused('%s is not a local user this may change' % name[:40])
    try:
        p = pwd.getpwnam(name)
    except KeyError:
        return None
    lo, hi = uid_range()
    if not lo <= p.pw_uid <= hi or p.pw_uid == 65534:
        raise Refused('%s is an account of the system (UID %d) - not changed here' % (name, p.pw_uid))
    return p


def lu_hash_checked(h):
    h = str(h or '')
    if not PW_HASH_RE.match(h):
        raise Refused('the password does not come as a hash this takes')
    return h


def lu_do(r):
    do = str(r.get('do') or 'list')
    name = str(r.get('name') or '')
    said = ''
    if do == 'list':
        return dict(lu_list(), said='')
    if do == 'keep':
        return dict(keep_read(), said='')
    if do == 'putback':
        said = keep_putback(r.get('keep') or {})
        return dict(lu_list(), said='; '.join(said))
    if do == 'policy':
        # The password policy (1.0.245): for every local user, not one.
        said = pwp_apply(r.get('conf') or {})
        return dict(lu_list(), said='; '.join(said))
    p = lu_target(name)
    if r.get('hash') or do == 'password':
        lu_hash_checked(r.get('hash'))          # before anything is done
    if do == 'add':
        lo, hi = uid_range()
        uid = r.get('uid')
        gecos = str(r.get('gecos') or '')
        shell = str(r.get('shell') or '/bin/bash')
        if not GECOS_RE.match(gecos):
            raise Refused('the full name has letters that cannot be in it (a colon, a line break)')
        if shell not in lu_shells():
            raise Refused('%s is not a shell of /etc/shells here' % shell[:60])
        if p is not None:
            # There already (both nodes of the sandbox are one machine, or asked again): the
            # same UID is no fault; another is said.
            if uid not in (None, '') and int(uid) != p.pw_uid:
                raise Refused('%s is here already, with UID %d (not %s)' % (name, p.pw_uid, uid))
            said = '%s was here already' % name
        else:
            argv = ['useradd', '-m', '-s', shell, '-c', gecos, '-U']
            if uid not in (None, ''):
                uid = int(uid)
                if not lo <= uid <= hi:
                    raise Refused('UID %d is not one of a normal user here (%d to %d)' % (uid, lo, hi))
                import pwd
                try:
                    other = pwd.getpwuid(uid).pw_name
                except KeyError:
                    other = ''
                if other:
                    raise Refused('UID %d is %s\'s here' % (uid, other))
                argv += ['-u', str(uid)]
            try:
                lu_run(argv + ['--', name])
                said = '%s made' % name
            except Exception as e:
                # Made in between by another ask (both nodes of the sandbox are one machine, or
                # the same ask twice at once, 1.0.248): there now, with the UID asked for, is no
                # fault - the same as "here already".
                import pwd
                try:
                    p = pwd.getpwnam(name)
                except KeyError:
                    raise e
                if uid not in (None, '') and int(uid) != p.pw_uid:
                    raise e
                said = '%s was here already' % name
        import pwd
        p = pwd.getpwnam(name)
        if not said.endswith('made'):
            # There already (1.0.248): its password, sudo and aging are not changed by an add -
            # "make alice on B too" sent to every node took her sudo away and her password on A.
            return dict(lu_list(), said=said)
        if r.get('hash'):
            lu_run(['chpasswd', '-e'], '%s:%s\n' % (name, lu_hash_checked(r['hash'])))
        else:
            # No password - a key (and otp's code) only (1.0.246): no password aging for it, or
            # once its days from login.defs ran out sshd would ask, at every sign-in by a key or
            # a code too, for a new password the user never had - and let nobody in.
            lu_run(['chage', '-M', '-1', '-I', '-1', name])
        if r.get('must_change') and r.get('hash'):     # never for one with no password (1.0.248)
            lu_run(['chage', '-d', '0', name])
        if r.get('sudo') is not None:
            lu_sudo(name, bool(r['sudo']))
        return dict(lu_list(), said=said)
    if p is None:
        if do == 'drop':
            return dict(lu_list(), said='%s was not here' % name)
        raise Refused('there is no user %s here' % name)
    if do == 'password':
        lu_run(['chpasswd', '-e'], '%s:%s\n' % (name, lu_hash_checked(r.get('hash'))))
        ag = r.get('policy_aging')
        if isinstance(ag, dict):
            # A password now (1.0.246): the policy's aging on it - a user of a key only had none.
            lu_run(['chage', '-M', str(pwp_int(ag.get('max_days'), 99999)), '-m', str(pwp_int(ag.get('min_days'), 0)),
                    '-W', str(pwp_int(ag.get('warn_days'), 7)), name])
        lu_run(['chage', '-d', '0' if r.get('must_change') else str(int(time.time() // 86400)), name])
        said = 'the password of %s set' % name
    elif do == 'lock':
        # The password and the account: no key lets in either (sshd asks PAM if it has expired).
        sh = lu_shadow().get(name, ('',))[0]
        if sh and not sh.startswith('!'):
            lu_run(['usermod', '-L', name])
        lu_run(['chage', '-E', '0', name])
        said = '%s locked' % name
    elif do == 'unlock':
        sh = lu_shadow().get(name, ('',))[0]
        # Every '!' (1.0.248): passwd -l on RHEL writes '!!', and usermod -U takes one away.
        for _ in range(4):
            if not (sh.startswith('!') and re.match(r'^\$[0-9a-z]{1,3}\$', sh.lstrip('!'))):
                break
            lu_run(['usermod', '-U', name])
            sh = lu_shadow().get(name, ('',))[0]
        lu_run(['chage', '-E', '-1', name])
        said = '%s unlocked' % name
    elif do == 'sudo':
        lu_sudo(name, bool(r.get('on')))
        said = '%s %s' % (name, 'may use sudo' if r.get('on') else 'no longer uses sudo')
    elif do == 'set':
        argv = ['usermod']
        if 'gecos' in r:
            g = str(r.get('gecos') or '')
            if not GECOS_RE.match(g):
                raise Refused('the full name has letters that cannot be in it (a colon, a line break)')
            # The pages show the name, the first of the fields (1.0.248): the same name saved
            # again kept "Room 12,555-1234" no longer.
            if g != p.pw_gecos.split(',')[0]:
                rest = p.pw_gecos.split(',', 1)[1:]
                argv += ['-c', ','.join([g] + rest) if rest and ',' not in g else g]
        if 'shell' in r:
            s = str(r.get('shell') or '')
            if s != p.pw_shell:             # the one it has, taken as it is (1.0.248)
                if s not in lu_shells():
                    raise Refused('%s is not a shell of /etc/shells here' % s[:60])
                argv += ['-s', s]
        if len(argv) > 1:
            lu_run(argv + ['--', name])
        said = '%s changed' % name
    elif do == 'aging':
        # Its own password aging (1.0.245): how long a password is good, the least between two
        # changes, the warning before it runs out.
        argv = ['chage']
        for k, opt, lo, hi in (('max_days', '-M', 0, 99999), ('min_days', '-m', 0, 365),
                               ('warn_days', '-W', 0, 365)):
            if k in r:
                v = pwp_int(r.get(k))
                if v is None or not lo <= v <= hi:
                    raise Refused('%s is %d to %d' % (k, lo, hi))
                argv += [opt, str(v)]
        if len(argv) > 1:
            lu_run(argv + [name])
        said = 'the password aging of %s set' % name
    elif do == 'drop':
        busy = subprocess.run(['pgrep', '-u', str(p.pw_uid)], capture_output=True, text=True)
        if busy.stdout.strip() and not r.get('force'):
            raise Refused('%s is signed in or runs something here - sign them out first' % name)
        lu_run(['userdel'] + (['-r'] if r.get('home') else []) + ['--', name])
        said = '%s taken away%s' % (name, ' with the home folder' if r.get('home') else '')
    else:
        raise Refused('list, add, password, lock, unlock, sudo, set, aging or drop')
    return dict(lu_list(), said=said)


def lu_sudo(name, on):
    g = lu_admin_group()
    if not g:
        raise Refused('this machine has no wheel or sudo group')
    import grp
    member = name in grp.getgrnam(g).gr_mem
    if on and not member:
        lu_run(['gpasswd', '-a', name, g])
    elif not on and member:
        lu_run(['gpasswd', '-d', name, g])


# ---- the password policy of the local users (1.0.245) ----------------------------------
# Settings -> Local users -> Password policy: one policy for the cluster, put in by each node's
# root helper into the system's own files - so that it holds however a password is changed
# (passwd, a password run out at sign-in, the pages): pam_pwquality's drop-in, pam_pwhistory's
# and pam_faillock's files (otp's lines between marks), login.defs' aging (the values before
# kept to be put back), and with authselect the features that put the modules in PAM. Not
# managed (the default): nothing is written, and what was written is taken out again.
SEC_DIR = os.environ.get('OTP_SECURITY_DIR', '/etc/security')
PAM_DIR = os.environ.get('OTP_PAM_DIR', '/etc/pam.d')
AUTHSELECT = os.environ.get('OTP_AUTHSELECT', shutil.which('authselect') or '')
PWQ_DROPIN = 'pwquality.conf.d/50-otp.conf'
PWP_MARK_A = '# ---- otp: Settings -> Local users -> Password policy (from here) ----\n'
PWP_MARK_B = '# ---- otp: (to here) ----\n'
# Which features of authselect otp switched on - in a folder of root's (1.0.248): in otp's own
# /var/lib/otp the service could write any feature there, and root switched it off at the next
# policy (nullok back, access.conf and faillock gone).
ROOT_STATE_DIR = os.environ.get('OTP_ROOT_STATE') or (
    '/var/lib/otp-root' if STATE_DIR == '/var/lib/otp' else STATE_DIR.rstrip('/') + '-root')
PWP_ORIG = os.environ.get('OTP_PWP_ORIG') or os.path.join(ROOT_STATE_DIR, 'pwpolicy-orig.json')
PWP_ORIG_OLD = '' if os.environ.get('OTP_PWP_ORIG') else os.path.join(STATE_DIR, 'pwpolicy-orig.json')
PWP_FEATURES = ('with-pwhistory', 'with-faillock')
PWQ_KEYS = ('minlen', 'minclass', 'maxrepeat', 'dictcheck', 'usercheck', 'enforce_for_root',
            'difok', 'retry', 'dcredit', 'ucredit', 'lcredit', 'ocredit', 'maxclassrepeat')
PWQ_DEFAULT = {'minlen': 8, 'minclass': 0, 'maxrepeat': 0, 'dictcheck': 1, 'usercheck': 1,
               'enforce_for_root': 0, 'difok': 1, 'retry': 1}
DEFS_KEYS = ('PASS_MAX_DAYS', 'PASS_MIN_DAYS', 'PASS_WARN_AGE')


def pwp_conf_read(path, flags=('enforce_for_root', 'even_deny_root', 'enforce_for_root')):
    """key = value lines (and lone flags) of a pam module's file, comments left out."""
    out = {}
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for ln in f:
                ln = ln.split('#', 1)[0].strip()
                if not ln:
                    continue
                if '=' in ln:
                    k, v = [x.strip() for x in ln.split('=', 1)]
                    out[k] = v
                elif ln in flags:
                    out[ln] = '1'
    except OSError:
        pass
    return out


def pwp_int(v, default=None):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


def pwp_pam():
    """Which of pwquality, pwhistory and faillock the PAM stack of the system uses."""
    files = ['system-auth', 'password-auth', 'common-password', 'common-auth', 'common-account']
    text = ''
    for f in files:
        try:
            with open(os.path.join(PAM_DIR, f), encoding='utf-8', errors='replace') as fh:
                text += fh.read() + '\n'
        except OSError:
            continue
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith('#')]
    has = lambda m: any(m in ln for ln in lines)
    return {'pwquality': has('pam_pwquality'), 'pwhistory': has('pam_pwhistory'),
            'faillock': has('pam_faillock'), 'read': bool(text.strip())}


def pwp_authselect():
    """(profile, features) of authselect, or None where it does not manage PAM."""
    if not AUTHSELECT or not os.path.exists(AUTHSELECT):
        return None
    got = subprocess.run([AUTHSELECT, 'current', '--raw'], capture_output=True, text=True, timeout=30)
    if got.returncode != 0 or not got.stdout.strip():
        return None
    words = got.stdout.split()
    return {'profile': words[0], 'features': words[1:]}


def pwp_read():
    """The policy as in effect on this node, read from its files."""
    pwq = dict(PWQ_DEFAULT)
    base = os.path.join(SEC_DIR, 'pwquality.conf')
    raw = pwp_conf_read(base)
    d = os.path.join(SEC_DIR, 'pwquality.conf.d')
    try:
        for name in sorted(os.listdir(d)):
            if name.endswith('.conf'):
                raw.update(pwp_conf_read(os.path.join(d, name)))
    except OSError:
        pass
    for k in PWQ_KEYS:
        if k in raw:
            pwq[k] = pwp_int(raw[k], raw[k])
    hist = pwp_conf_read(os.path.join(SEC_DIR, 'pwhistory.conf'))
    fl = pwp_conf_read(os.path.join(SEC_DIR, 'faillock.conf'), flags=('even_deny_root', 'silent', 'audit'))
    defs = {}
    try:
        for ln in open(LOGIN_DEFS, encoding='utf-8', errors='replace'):
            w = ln.split()
            if len(w) >= 2 and w[0] in DEFS_KEYS:
                defs[w[0]] = pwp_int(w[1], w[1])
    except OSError:
        pass
    pam = pwp_pam()
    return {'pwquality': pwq, 'remember': pwp_int(hist.get('remember'), 10 if pam['pwhistory'] else 0),
            'faillock': {'deny': pwp_int(fl.get('deny'), 3), 'unlock_time': pwp_int(fl.get('unlock_time'), 600),
                         'fail_interval': pwp_int(fl.get('fail_interval'), 900)},
            'aging': {'max_days': defs.get('PASS_MAX_DAYS', 99999), 'min_days': defs.get('PASS_MIN_DAYS', 0),
                      'warn_days': defs.get('PASS_WARN_AGE', 7)},
            'pam': pam, 'authselect': pwp_authselect(),
            'managed': os.path.exists(os.path.join(SEC_DIR, PWQ_DROPIN)),
            'pwscore': bool(shutil.which('pwscore'))}


def pwp_block_put(path, lines):
    """otp's lines between the marks in a file of the system: put in, replaced, or (None) taken out;
    the rest of the file as it is. A file that is not there is made only to put lines in."""
    try:
        st = os.lstat(path)
        if not stat.S_ISREG(st.st_mode):
            raise Refused('%s is not a plain file - not written' % path)
        with open(path, encoding='utf-8', errors='replace') as f:
            text = f.read()
        mode = stat.S_IMODE(st.st_mode)
    except FileNotFoundError:
        if lines is None:
            return
        text, mode = '', 0o644
    a, b = text.find(PWP_MARK_A), text.find(PWP_MARK_B)
    if lines is None and not (a >= 0 and b > a):
        return                          # none of otp's there: the file left as it is
    was = text
    if a >= 0 and b > a:
        text = text[:a] + text[b + len(PWP_MARK_B):]
    if lines is not None:
        if text and not text.endswith('\n'):
            text += '\n'
        text += PWP_MARK_A + ''.join('%s\n' % ln for ln in lines) + PWP_MARK_B
    if text != was:
        write_root(path, text, mode)


def pwp_defs_put(values):
    """login.defs' aging lines set (values) or put back as they were (None). The lines as they were
    are kept in login.defs itself, commented between otp's marks - so that whatever node or copy of
    the state puts it back, it is what the machine had (1.0.245)."""
    with open(LOGIN_DEFS, encoding='utf-8', errors='replace') as f:
        text = f.read()
    a, b = text.find(PWP_MARK_A), text.find(PWP_MARK_B)
    was = {}
    if a >= 0 and b > a:
        for ln in text[a + len(PWP_MARK_A):b].split('\n'):
            if ln.startswith('# otp-was: '):
                k, _, line = ln[len('# otp-was: '):].partition(' ')
                if k in DEFS_KEYS:
                    was[k] = line                   # '' - there was no such line
        text = text[:a] + text[b + len(PWP_MARK_B):]
    lines = text.split('\n')
    if values is not None and not was:
        for k in DEFS_KEYS:
            was[k] = next((ln for ln in lines if ln.split()[:1] == [k]), '')
    out, seen = [], set()
    for ln in lines:
        w = ln.split()
        if w and w[0] in DEFS_KEYS:
            if values is not None:
                if w[0] not in seen:
                    out.append('%s\t%s' % (w[0], values[w[0]]))
                seen.add(w[0])
                continue
            if w[0] in was:
                if w[0] not in seen and was[w[0]]:
                    out.append(was[w[0]])
                seen.add(w[0])
                continue
        out.append(ln)
    if values is not None:
        for k in DEFS_KEYS:
            if k not in seen:
                out.append('%s\t%s' % (k, values[k]))
        text = '\n'.join(out)
        if not text.endswith('\n'):
            text += '\n'
        text += PWP_MARK_A + ''.join('# otp-was: %s %s\n' % (k, was.get(k, '')) for k in DEFS_KEYS) + PWP_MARK_B
    else:
        for k in DEFS_KEYS:
            if k in was and was[k] and k not in seen:
                out.append(was[k])
        text = '\n'.join(out)
    st = os.stat(LOGIN_DEFS)
    write_root(LOGIN_DEFS, text, stat.S_IMODE(st.st_mode))


def pwp_orig_read():
    """What otp switched on, as root kept it - only features otp switches on at all."""
    got = {}
    for p in (PWP_ORIG, PWP_ORIG_OLD):
        if not p:
            continue
        try:
            # Not waited on (1.0.249): a FIFO put there held the helper, and every ask after it.
            fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd) as f:
                st = os.fstat(f.fileno())
                if not stat.S_ISREG(st.st_mode):
                    continue
                # The one of the service's folder only as root wrote it (1.0.248): one of the
                # otp account's own there is no word of root's.
                if p == PWP_ORIG_OLD and st.st_uid != 0:
                    continue
                got = json.load(f)
            break
        except (OSError, ValueError):
            continue
    if not isinstance(got, dict):
        got = {}
    got['features'] = [f for f in (got.get('features') or []) if f in PWP_FEATURES]
    if not got['features']:
        got.pop('features')
    return got


def pwp_orig_write(orig):
    if orig:
        if os.path.dirname(PWP_ORIG) == ROOT_STATE_DIR:
            os.makedirs(ROOT_STATE_DIR, mode=0o700, exist_ok=True)
            os.chmod(ROOT_STATE_DIR, 0o700)
        write_root(PWP_ORIG, json.dumps(orig), 0o600)
    else:
        try:
            os.unlink(PWP_ORIG)
        except OSError:
            pass
    if PWP_ORIG_OLD:
        try:
            os.unlink(PWP_ORIG_OLD)     # the one of the service's folder, before 1.0.248
        except OSError:
            pass


def pwp_checked(c):
    """The policy as asked, every value in its range - refused otherwise."""
    if not isinstance(c, dict):
        raise Refused('the policy is not an object')

    def num(k, lo, hi, default):
        v = c.get(k, default)
        try:
            v = int(v)
        except (TypeError, ValueError):
            raise Refused('%s is a number' % k)
        if not lo <= v <= hi:
            raise Refused('%s is %d to %d' % (k, lo, hi))
        return v
    return {'managed': bool(c.get('managed')),
            'minlen': num('minlen', 6, 128, 12), 'minclass': num('minclass', 0, 4, 3),
            'maxrepeat': num('maxrepeat', 0, 20, 3), 'dictcheck': 1 if c.get('dictcheck', 1) else 0,
            'usercheck': 1 if c.get('usercheck', 1) else 0, 'difok': num('difok', 0, 20, 5),
            'remember': num('remember', 0, 50, 5),
            'max_days': num('max_days', 0, 99999, 99999), 'min_days': num('min_days', 0, 365, 0),
            'warn_days': num('warn_days', 0, 365, 7),
            'deny': num('deny', 0, 100, 0), 'unlock_time': num('unlock_time', 0, 86400, 900),
            'fail_interval': num('fail_interval', 60, 86400, 900),
            'existing': bool(c.get('existing'))}


def pwp_apply(c):
    """Put the policy in (managed) or take otp's out again (not managed)."""
    import pwd
    c = pwp_checked(c)
    said = []
    orig = pwp_orig_read()
    sel = pwp_authselect()
    added = list(orig.get('features') or [])
    dropin = os.path.join(SEC_DIR, PWQ_DROPIN)
    if not c['managed']:
        try:
            os.unlink(dropin)
            said.append('pwquality: otp\'s drop-in taken out')
        except FileNotFoundError:
            pass
        for f in ('pwhistory.conf', 'faillock.conf'):
            pwp_block_put(os.path.join(SEC_DIR, f), None)
        if PWP_MARK_A in open(LOGIN_DEFS, encoding='utf-8', errors='replace').read():
            pwp_defs_put(None)
            said.append('login.defs: the aging as it was')
        if sel:
            for feat in added:
                if feat in sel['features']:
                    lu_run([AUTHSELECT, 'disable-feature', feat])
                    said.append('authselect: %s taken out again' % feat)
        orig = pwp_orig_read()
        orig.pop('features', None)
        pwp_orig_write(orig)
        return said or ['nothing of otp\'s was there']
    os.makedirs(os.path.dirname(dropin), exist_ok=True)
    write_root(dropin, '# written by otp - Settings -> Local users -> Password policy\n'
               'minlen = %(minlen)d\nminclass = %(minclass)d\nmaxrepeat = %(maxrepeat)d\n'
               'dictcheck = %(dictcheck)d\nusercheck = %(usercheck)d\ndifok = %(difok)d\n'
               'retry = 3\n' % c, 0o644)
    said.append('pwquality: at least %d characters, %d kinds' % (c['minlen'], c['minclass']))
    pwp_block_put(os.path.join(SEC_DIR, 'pwhistory.conf'),
                  ['remember = %d' % c['remember']] if c['remember'] else None)
    pwp_block_put(os.path.join(SEC_DIR, 'faillock.conf'),
                  ['deny = %d' % c['deny'], 'unlock_time = %d' % c['unlock_time'],
                   'fail_interval = %d' % c['fail_interval']] if c['deny'] else None)
    pwp_defs_put({'PASS_MAX_DAYS': c['max_days'], 'PASS_MIN_DAYS': c['min_days'],
                  'PASS_WARN_AGE': c['warn_days']})
    said.append('login.defs: a password good for %s days' % (c['max_days'] if c['max_days'] < 99999 else 'all'))
    if sel:
        want = (['with-pwhistory'] if c['remember'] else []) + (['with-faillock'] if c['deny'] else [])
        def note():
            # Kept at once (1.0.248): written only at the end, one switched on before a later
            # step failed was never noted - and never switched off again.
            o = pwp_orig_read()
            o['features'] = added
            pwp_orig_write(o)
        for feat in want:
            if feat not in sel['features']:
                added.append(feat)
                note()
                lu_run([AUTHSELECT, 'enable-feature', feat])
                said.append('authselect: %s put in' % feat)
        for feat in [f for f in added if f not in want]:
            if feat in sel['features']:
                lu_run([AUTHSELECT, 'disable-feature', feat])
                said.append('authselect: %s taken out again' % feat)
            added = [f for f in added if f != feat]
        note()
    if c['existing']:
        lo, hi = uid_range()
        n = skipped = 0
        sh = lu_shadow()
        for p in pwd.getpwall():
            if lo <= p.pw_uid <= hi and p.pw_uid != 65534 and p.pw_name not in KEEP_NAMES and \
                    USER_NAME_RE.match(p.pw_name):
                if not sh.get(p.pw_name, ('',))[0].lstrip('!').startswith('$'):
                    skipped += 1        # no password: a key only - never asked for a new one
                    continue
                lu_run(['chage', '-M', str(c['max_days']), '-m', str(c['min_days']),
                        '-W', str(c['warn_days']), p.pw_name])
                n += 1
        said.append('the aging put on %d user(s) of this node too%s' % (
            n, ' (%d with no password - a key only - left without)' % skipped if skipped else ''))
    return said

# ---- what of the machine is kept for a backup (1.0.247) ---------------------------------
# The machine's own, which no row of the database holds: the local users (their UID, full name,
# shell, password's hash, aging, sudo), the SSH keys root and each of them sign in with, and the
# booleans of SELinux otp needs. Read here ("keep") and sealed into the database by the daemon, so
# that a backup carries it; put back ("putback") on a machine installed anew - users made where
# they are missing, keys added where missing, nothing taken away.
SEL_BOOLS = ('httpd_can_network_connect', 'authlogin_radius')


def keep_read():
    import pwd
    import grp
    lo, hi = uid_range()
    sh = {}
    try:
        with open(SHADOW, encoding='utf-8', errors='replace') as f:
            for ln in f:
                p = ln.rstrip('\n').split(':')
                if len(p) >= 8:
                    sh[p[0]] = p
    except OSError:
        pass
    admin = lu_admin_group()
    users, keys = [], {}
    for p in pwd.getpwall():
        if not (lo <= p.pw_uid <= hi) or p.pw_uid == 65534 or p.pw_name in KEEP_NAMES or \
                not USER_NAME_RE.match(p.pw_name):
            continue
        s = sh.get(p.pw_name) or [''] * 9
        groups = sorted(g.gr_name for g in grp.getgrall() if p.pw_name in g.gr_mem)
        users.append({'name': p.pw_name, 'uid': p.pw_uid, 'gecos': p.pw_gecos, 'shell': p.pw_shell,
                      'hash': s[1], 'lastchg': s[2], 'min': s[3], 'max': s[4], 'warn': s[5],
                      'inactive': s[6], 'expire': s[7], 'sudo': bool(admin) and admin in groups})
        try:
            lines = user_auth_read(p)
            if lines:
                # Only the lines put back (1.0.252): junk lines of a user's own made the keep too
                # big to be read back, and nobody's users or keys were put back.
                keys[p.pw_name] = keep_lines_short(lines)
        except Exception:                               # noqa: BLE001
            pass
    try:
        root = keep_lines_short(auth_lines())
    except Exception:                                   # noqa: BLE001
        root = []
    sel = {}
    if shutil.which('getsebool'):
        for b in SEL_BOOLS:
            got = subprocess.run(['getsebool', b], capture_output=True, text=True)
            if got.returncode == 0:
                sel[b] = got.stdout.strip().endswith('on')
    # SELinux's mode as well (1.0.268): a machine installed anew and put back from a backup comes
    # up as its system has it - the page says it was enforcing here, and how to get it back.
    se_mode = ''
    if shutil.which('getenforce'):
        try:
            se_mode = subprocess.run(['getenforce'], capture_output=True, text=True,
                                     timeout=30).stdout.strip()[:20]
        except (OSError, subprocess.SubprocessError):
            se_mode = ''
    return {'users': users[:500], 'keys': keys, 'root_keys': root, 'selinux': sel,
            'selinux_mode': se_mode, 'admin_group': admin, 'at': time.time()}


def keep_lines_short(lines):
    """The lines of an authorized_keys kept, 200 at most, none longer than a key can be (1.0.252):
    a user's own junk lines made the keep too big to be read back, and nobody's users or keys
    were put back. Lines with options stay kept - counted, when put back, as not put back."""
    out, size = [], 0
    for ln in lines:
        if not ln.strip() or ln.lstrip().startswith('#') or len(ln) > 16500:
            continue
        size += len(ln)
        if len(out) >= 200 or size > 256 * 1024:
            break
        out.append(ln)
    return out


def keep_key_lines(lines):
    """The lines of a kept authorized_keys that are put back: one public key each, of a kind
    taken here, nothing before it (1.0.248) - options (command=, from=...) are added by hand."""
    good, other = [], 0
    for ln in lines[:200]:
        ln = str(ln).strip()
        if not ln or ln.startswith('#'):
            continue
        m = KEY_LINE_RE.match(ln)
        if m and m.group('type') in KEY_TYPES and '\n' not in ln and len(ln) <= 16500:
            good.append(ln)
        else:
            other += 1
    return good, other


def keep_putback(k):
    """What a backup kept of this machine, put back: only what is missing - never a user, key or
    setting of the machine as it is now taken away or changed. Each user on its own (1.0.248): one
    that could not be made stopped the rest, root's keys and the booleans."""
    import pwd
    if not isinstance(k, dict):
        raise Refused('nothing to put back')
    lo, hi = uid_range()
    said, made, keys_n, skipped, failed = [], 0, 0, 0, []
    for u in (k.get('users') or [])[:500]:
        if not isinstance(u, dict):
            continue
        name = str(u.get('name') or '')
        if not USER_NAME_RE.match(name) or name in KEEP_NAMES:
            continue
        try:
            uid = int(u.get('uid'))
        except (TypeError, ValueError):
            continue
        if not lo <= uid <= hi or uid == 65534:
            continue
        try:
            try:
                p = pwd.getpwnam(name)
            except KeyError:
                p = None
            if p is None:
                try:
                    other = pwd.getpwuid(uid).pw_name
                except KeyError:
                    other = ''
                shell = str(u.get('shell') or '/bin/bash')
                # A shell that lets nobody in (nologin, false) kept as it is, where it is here: a user
                # of SFTP only made again with bash could sign in (1.0.248).
                # Only the known paths of those (1.0.249): /tmp/nologin, any script so named, was
                # taken - and ran at every sign-in of that user.
                if shell not in lu_shells() and not (shell in NOLOGIN_PATHS and os.path.isfile(shell)):
                    shell = '/bin/bash' if not os.path.basename(shell) in NO_SHELLS else \
                        next((x for x in ('/usr/sbin/nologin', '/sbin/nologin', '/bin/false')
                              if os.path.isfile(x)), '/bin/false')
                gecos = str(u.get('gecos') or '')[:120]
                if not GECOS_RE.match(gecos):
                    gecos = re.sub(r'[:\n\x00-\x1f\x7f]', ' ', gecos)[:120]
                argv = ['useradd', '-m', '-s', shell, '-c', gecos, '-U']
                if not other:
                    argv += ['-u', str(uid)]
                lu_run(argv + ['--', name])
                h = str(u.get('hash') or '')
                if PW_HASH_RE.match(h.lstrip('!')):
                    lu_run(['chpasswd', '-e'], '%s:%s\n' % (name, h.lstrip('!')))
                    if h.startswith('!'):
                        lu_run(['usermod', '-L', name])
                # The aging as it was - the day of the last change, the days, the account's end.
                args = ['chage']
                for opt, key in (('-d', 'lastchg'), ('-m', 'min'), ('-M', 'max'), ('-W', 'warn'),
                                 ('-I', 'inactive'), ('-E', 'expire')):
                    v = str(u.get(key) or '')
                    args += [opt, v if re.match(r'^-?\d{1,6}\Z', v) else '-1']
                lu_run(args + [name])
                if u.get('sudo'):
                    try:
                        lu_sudo(name, True)
                    except Refused:
                        pass
                made += 1
                said.append('%s made again%s' % (name, '' if not other else ' (UID %d was %s\'s here)' % (uid, other)))
            elif p.pw_uid != uid:
                # Somebody else of that name here (1.0.248) - a system account of the new
                # machine, say: never given the kept user's keys.
                said.append('%s is here with UID %d (kept: %d) - left as it is' % (name, p.pw_uid, uid))
                continue
            lines, other_n = keep_key_lines((k.get('keys') or {}).get(name) or [])
            skipped += other_n
            if lines:
                # The user of this machine of that name and the kept UID (checked above): its own
                # home folder, written as the user (user_auth_write refuses another's).
                pw = pwd.getpwnam(name)
                if not lo <= pw.pw_uid <= hi or pw.pw_uid == 65534 or not pw.pw_dir.startswith('/') or \
                        pw.pw_dir == '/':
                    raise Refused('%s is no normal user here' % name)
                have = user_auth_read(pw)
                add = [ln for ln in lines if ln not in have]
                if add:
                    user_auth_write(pw, [ln for ln in have if ln.strip()] + add)
                    keys_n += len(add)
        except (Refused, OSError, subprocess.SubprocessError) as e:
            failed.append('%s: %s' % (name, str(e)[:160]))
    try:
        root, other_n = keep_key_lines(k.get('root_keys') or [])
        skipped += other_n
        if root:
            have = auth_lines()
            add = [ln for ln in root if ln not in have]
            if add:
                auth_write([ln for ln in have if ln.strip()] + add)
                keys_n += len(add)
                said.append('%d key(s) of root put back' % len(add))
    except (Refused, OSError) as e:
        failed.append('root\'s keys: %s' % str(e)[:160])
    for b, on in (k.get('selinux') or {}).items():
        if b in SEL_BOOLS and on and shutil.which('setsebool'):
            try:
                got = subprocess.run(['getsebool', b], capture_output=True, text=True, timeout=60)
                if got.returncode == 0 and not got.stdout.strip().endswith('on'):
                    subprocess.run(['setsebool', '-P', b, 'on'], capture_output=True, text=True, timeout=300)
                    said.append('SELinux: %s on' % b)
            except (OSError, subprocess.SubprocessError) as e:
                failed.append('SELinux %s: %s' % (b, str(e)[:120]))
    if skipped:
        said.append('%d key line(s) with options before the key (or not one key) left out - put '
                    'those in by hand' % skipped)
    if failed:
        said.append('not put back: ' + '; '.join(failed[:10]))
    said.insert(0, '%d user(s) made again, %d SSH key(s) put back' % (made, keys_n))
    return said


def users_part():
    d = web_fd()
    try:
        # 16 MB (1.0.252): a machine's keep put back - its users and their keys - can be more than 4.
        raw = read_req(USERS_ASK, 16 * 1024 * 1024)
    except FileNotFoundError:
        return
    except (Refused, OSError):
        drop_ask(USERS_ASK, d)
        return
    drop_ask(USERS_ASK, d)
    out = {'at': time.time(), 'ok': False, 'id': ''}
    try:
        r = json.loads(raw.decode('utf-8'))
        if not isinstance(r, dict):
            raise Refused('the request is not an object')
        out['id'] = re.sub(r'[^A-Za-z0-9]', '', str(r.get('id') or ''))[:40]
        out['data'] = lu_do(r)
        out['ok'] = True
    except Refused as e:
        out['said'] = str(e)[:400]
    except Exception as e:                              # noqa: BLE001
        out['said'] = 'it went wrong: %s' % str(e)[:300]
    write_here(USERS_FILE, json.dumps(out))

# ---- the SSH server and the notices at sign-in (1.0.163) --------------------------------
# otp's own drop-in, read before every other (00-otp.conf: the first value
# sshd reads of a setting is the one it keeps), checked by sshd -t before it
# is put in, and on trial: a timer of systemd's own puts the one before back
# unless Keep it comes in time - also with the daemon down, also with the
# web away. The notices: before signing in over SSH (Banner), at the console
# (/etc/issue.d or /etc/issue) and after signing in (/etc/motd.d or /etc/motd).
SSHD_ASK, SSHD_FILE = 'sshd.ask', 'sshd.json'
SSH_DIR = os.environ.get('OTP_SSH_DIR', '/etc/ssh')
ETC_DIR = os.environ.get('OTP_ETC', '/etc')
SSHD_BIN = shutil.which('sshd') or '/usr/sbin/sshd'
SSHD_DROPIN = 'sshd_config.d/00-otp.conf'
SSHD_STATE = os.path.join(SSH_DIR, '.otp-sshd-trial.json')
SSHD_PERMIT = ('yes', 'prohibit-password', 'no')
NOTICE_MARK = '# written by otp - Settings -> SSH server and notices\n'


def sshd_conf_path():
    return os.path.join(SSH_DIR, 'sshd_config')


def sshd_reads_dropins():
    """Whether sshd_config takes sshd_config.d (OpenSSH 8.2 on; RHEL 8's 8.0 does not)."""
    try:
        with open(sshd_conf_path()) as f:
            text = f.read()
    except OSError:
        return False
    return bool(re.search(r'(?im)^\s*Include\s+\S*sshd_config\.d/\*\.conf', text))


def sshd_values():
    if not os.path.exists(SSHD_BIN):
        return {}
    got = subprocess.run([SSHD_BIN, '-T', '-f', sshd_conf_path(), '-C',
                          'user=root,host=localhost,addr=127.0.0.1'],
                         capture_output=True, text=True, timeout=20)
    said = {}
    for ln in got.stdout.splitlines():
        k, _, v = ln.partition(' ')
        if k in ('port', 'permitrootlogin', 'passwordauthentication', 'pubkeyauthentication',
                 'allowusers', 'banner', 'kbdinteractiveauthentication', 'maxauthtries'):
            said[k] = v.strip() if k not in said else said[k] + ' ' + v.strip()
    return said


def _read_or(path, most=65536):
    # A plain file only (1.0.205): a FIFO put there held the helper - and every
    # request behind it - for good.
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            return None
        with os.fdopen(fd, 'rb') as f:
            return f.read(most).decode('utf-8', 'replace')
    except OSError:
        return None


def _put_file(path, text, mode=0o644):
    """Written whole, beside and renamed in; never through a link."""
    folder = os.path.dirname(path)
    if os.path.islink(path) or os.path.islink(folder):
        raise Refused('%s is a link - put the file itself there' % path)
    os.makedirs(folder, mode=0o755, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix='.otp-')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(text)
            # On the file itself, not by its name (1.0.205): /etc/otp is the otp
            # group's to write in, and a link put in place of the temporary file
            # had root change the mode of whatever it pointed at.
            f.flush()
            os.fchmod(f.fileno(), mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    if shutil.which('restorecon'):
        subprocess.run(['restorecon', path], capture_output=True)


def _drop(path):
    try:
        if not os.path.islink(path):
            os.unlink(path)
    except FileNotFoundError:
        pass


def notice_paths():
    """Where the console's and the after-sign-in notices go here: a file of
    otp's own in issue.d / motd.d where agetty and pam_motd read those, else
    the one file (kept as it was beside it, put back when switched off)."""
    issue_d = os.path.join(ETC_DIR, 'issue.d')
    motd_d = os.path.join(ETC_DIR, 'motd.d')
    return {'issue': os.path.join(issue_d, 'otp.issue') if os.path.isdir(issue_d)
            else os.path.join(ETC_DIR, 'issue'),
            'motd': os.path.join(motd_d, 'otp') if os.path.isdir(motd_d)
            else os.path.join(ETC_DIR, 'motd'),
            'banner': os.path.join(SSH_DIR, 'otp-banner')}


def notice_set(where, text):
    """The notice put in at `where` (issue, motd), or taken out (text None)."""
    path = notice_paths()[where]
    whole = os.path.basename(path) in ('issue', 'motd')
    keep = path + '.otp-before'
    if text is None:
        if whole:
            had = _read_or(keep)
            cur = _read_or(path) or ''
            if had is not None and cur.startswith(NOTICE_MARK.strip()):
                _put_file(path, had)
            _drop(keep)
        else:
            _drop(path)
        return
    if whole and _read_or(keep) is None:
        cur = _read_or(path)
        if cur is not None and not cur.startswith(NOTICE_MARK.strip()):
            _put_file(keep, cur)
    body = text.rstrip() + '\n'
    if where == 'issue':
        body = body.replace('\\', '\\\\') + '\n'       # agetty reads \ escapes
    _put_file(path, (NOTICE_MARK if whole else '') + body)


def root_keys_count():
    try:
        return len([k for k in auth_keys(auth_lines()) if k.get('readable')])
    except Exception:                                   # noqa: BLE001
        return 0


def sshd_checked(c):
    """What the page asked for, made whole - checked here again."""
    if not isinstance(c, dict):
        raise Refused('the request is not an object')
    out = {'manage': bool(c.get('manage'))}
    permit = str(c.get('permit_root') or 'prohibit-password')
    if permit not in SSHD_PERMIT:
        raise Refused('root signs in with: yes, prohibit-password or no')
    out['permit_root'] = permit
    out['password'] = bool(c.get('password'))
    try:
        port = int(c.get('port') or 22)
    except (TypeError, ValueError):
        raise Refused('the port is a number')
    if not 1 <= port <= 65535:
        raise Refused('the port is 1 to 65535')
    # Not a port another service of this machine listens on (1.0.234): sshd could not bind it and
    # stopped - and under SELinux the port was labelled for ssh, away from its own service.
    taken = {80: 'the web server', 443: 'the web server', 1812: 'RADIUS', 1813: 'RADIUS',
             1645: 'RADIUS', 1646: 'RADIUS', 5432: 'PostgreSQL', 3306: 'MariaDB',
             25: 'mail', 53: 'DNS', 123: 'the time', 161: 'SNMP', 162: 'SNMP', 514: 'syslog',
             6514: 'syslog', 9861: 'otp\'s API', 112: 'keepalived'}
    if port in taken:
        raise Refused('port %d is %s\'s - choose another for SSH' % (port, taken[port]))
    out['port'] = port
    raw = c.get('allow_users') or ''
    # A list from the daemon (1.0.164: read as the text "['root']" before).
    users = [str(u) for u in raw if u] if isinstance(raw, list) else \
        [u for u in re.split(r'[\s,]+', str(raw)) if u]
    for u in users:
        if not re.match(r'^[A-Za-z0-9._@*?-]{1,64}\Z', u):
            raise Refused('%r is not a user name' % u)
    out['allow_users'] = users[:50]
    try:
        out['tries'] = max(1, min(10, int(c.get('tries') or 4)))
    except (TypeError, ValueError):
        out['tries'] = 4
    text = str(c.get('notice') or '').replace('\r\n', '\n')
    if len(text) > 4000:
        raise Refused('the notice is 4000 characters at most')
    if re.search(r'[\x00-\x08\x0b-\x1f\x7f]', text):
        raise Refused('no control characters in the notice')
    out['notice'] = text
    for k in ('notice_ssh', 'notice_console', 'notice_motd'):
        out[k] = bool(c.get(k)) and bool(text.strip())
    out['radius'] = bool(c.get('radius')) and out['manage']
    raw = c.get('radius_users') or []
    ru = [str(u) for u in raw if u] if isinstance(raw, list) else \
        [u for u in re.split(r'[\s,]+', str(raw)) if u]
    for u in ru:
        if not re.match(r'^[A-Za-z0-9._@-]{1,64}\Z', u):
            raise Refused('%r is not a user name' % u)
    out['radius_users'] = ru[:100]
    out['radius_root'] = bool(c.get('radius_root'))
    out['radius_fallback'] = bool(c.get('radius_fallback')) and out['password']
    # A key and then the code (1.0.183): AuthenticationMethods for those asked.
    out['radius_with_key'] = bool(c.get('radius_with_key')) and out['radius']
    out['radius_hide'] = bool(c.get('radius_hide')) and out['radius']
    return out


# ---- SSH with a code from otp (1.0.178) ------------------------------------------------
# pam_radius in sshd's PAM: a block of otp's own at the top of the auth lines
# of /etc/pam.d/sshd, asking this node's RADIUS on 127.0.0.1 with the secret in
# /etc/otp/pam_radius.conf (0600). Root is left out unless asked; a key goes
# past PAM as always. With passwords off, nobody gets in by a password through
# PAM either. Put back with the rest when a change on trial is not kept.
PAM_BEGIN = '# otp: SSH with a code from otp (RADIUS) - Settings -> SSH server (begin)'
PAM_END = '# otp: SSH with a code from otp (RADIUS) (end)'
PAM_MOD_DIRS = ('/usr/lib64/security', '/lib64/security', '/usr/lib/x86_64-linux-gnu/security',
                '/lib/x86_64-linux-gnu/security', '/usr/lib/aarch64-linux-gnu/security',
                '/usr/lib/security', '/lib/security')


def pam_sshd_path():
    return os.path.join(ETC_DIR, 'pam.d', 'sshd')


def pam_radius_conf_path():
    return os.path.join(ETC_DIR, 'otp', 'pam_radius.conf')


def pam_radius_module():
    for d in PAM_MOD_DIRS:
        if os.path.exists(os.path.join(d, 'pam_radius_auth.so')):
            return os.path.join(d, 'pam_radius_auth.so')
    return ''


def pam_radius_install():
    """The module put in where it is missing - EPEL's pam_radius, Debian's
    libpam-radius-auth."""
    if pam_radius_module() or os.environ.get('OTP_NO_PKG'):
        return pam_radius_module()
    for cmd in (['dnf', '-y', 'install', 'pam_radius'],
                ['apt-get', '-y', 'install', 'libpam-radius-auth']):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            break
    if not pam_radius_module():
        raise Refused('pam_radius is not on this machine and could not be put in - on '
                      'AlmaLinux/RHEL: dnf install epel-release && dnf install pam_radius')
    return pam_radius_module()


def pam_without_ours(text):
    return re.sub(r'(?ms)^' + re.escape(PAM_BEGIN) + r'\n.*?^' + re.escape(PAM_END) + r'\n?', '',
                  text)


def pam_block(c):
    lines = [PAM_BEGIN]
    if c['radius_users']:
        lines.append('auth [success=1 default=ignore] pam_succeed_if.so quiet user notin %s'
                     % ':'.join(c['radius_users']))
    elif not c['radius_root']:
        lines.append('auth [success=1 default=ignore] pam_succeed_if.so quiet user = root')
    # skip_passwd (1.0.188): no "Password:" first - otp's gate asks for the code
    # itself (the app's, or one it mails or texts), in the one prompt it shows.
    lines.append('auth [success=done new_authtok_reqd=done ignore=ignore default=die] '
                 'pam_radius_auth.so conf=%s skip_passwd prompt_attribute%s' % (pam_radius_conf_path(),
                                                               ' localifdown' if c['radius_fallback'] else ''))
    if c['radius_fallback'] and sshd_root_code_key_only(c):
        # otp not answering (1.0.191): root, made to reach PAM for its code, gets
        # no system password - it signs in with a key only, as set.
        lines.append('auth [success=ignore default=die] pam_succeed_if.so quiet user != root')
    if not c['password']:
        # Passwords off: nobody left out of the code gets in by a password here.
        lines.append('auth requisite pam_deny.so')
    lines.append(PAM_END)
    return '\n'.join(lines) + '\n'


def pam_selinux_radius():
    """SELinux keeps sshd from asking RADIUS until authlogin_radius is on."""
    if os.environ.get('OTP_NO_PKG') or not shutil.which('getsebool') or not shutil.which('getenforce'):
        return
    if subprocess.run(['getenforce'], capture_output=True, text=True).stdout.strip() == 'Disabled':
        return
    got = subprocess.run(['getsebool', 'authlogin_radius'], capture_output=True, text=True)
    if got.returncode or got.stdout.strip().endswith('on'):
        return
    got = subprocess.run(['setsebool', '-P', 'authlogin_radius', 'on'], capture_output=True, text=True,
                         timeout=300)
    if got.returncode:
        raise Refused('SELinux: setsebool -P authlogin_radius on: %s'
                      % (got.stderr or got.stdout).strip()[-200:])


def pam_radius_conf_write(secret, port):
    if not re.match(r'^[\x21-\x7e]{8,128}\Z', str(secret or '')):
        raise Refused('the secret of otp\'s gate for SSH is missing')
    os.makedirs(os.path.dirname(pam_radius_conf_path()), mode=0o755, exist_ok=True)
    _put_file(pam_radius_conf_path(), '# otp - Settings -> SSH server; the secret of otp\'s gate '
              'for SSH on 127.0.0.1\n'
              # The source as a fourth field (1.0.178): pam_radius 2.0.1 with
              # three closed this file twice and took sshd's process down.
              '127.0.0.1:%d %s 30 127.0.0.1\n' % (int(port or 18129), secret), 0o600)


def pam_radius_conf_fp():
    """What the daemon compares with its own: a hash of the port and the
    secret pam_radius has, never the secret."""
    for line in (_read_or(pam_radius_conf_path()) or '').split('\n'):
        m = re.match(r'^127\.0\.0\.1:(\d+)\s+(\S+)', line)
        if m:
            return hashlib.sha256(('%d %s' % (int(m.group(1)), m.group(2))).encode()).hexdigest()[:12]
    return ''


def pam_skip_passwd(text):
    """Our block's pam_radius line with skip_passwd (1.0.188) and prompt_attribute
    (1.0.191: the code hidden as typed, where set), the rest as it is."""
    def one(m):
        block = m.group(0)
        for opt in ('skip_passwd', 'prompt_attribute'):
            block = re.sub(r'(?m)^(auth\b.*pam_radius_auth\.so conf=\S+)(?!.*\b%s\b)(.*)$' % opt,
                           r'\1 %s\2' % opt, block)
        return block
    return re.sub(r'(?ms)^' + re.escape(PAM_BEGIN) + r'\n.*?^' + re.escape(PAM_END) + r'$', one, text)


def pam_set(c, secret, port):
    """Our block in (or out of) sshd's PAM; the secret's file with it."""
    path = pam_sshd_path()
    text = _read_or(path)
    if text is None:
        if not c.get('radius'):
            return ''
        raise Refused('%s is not there - sshd does not use PAM here' % path)
    clean = pam_without_ours(text)
    if not c.get('radius'):
        if clean != text:
            _put_file(path, clean, 0o644)
        _drop(pam_radius_conf_path())
        return 'SSH without a code from otp' if clean != text else ''
    pam_radius_install()
    pam_selinux_radius()
    pam_radius_conf_write(secret, port)
    lines = clean.split('\n')
    at = next((i for i, l in enumerate(lines)
               if re.match(r'^\s*(auth\b|@include\s+common-auth|-?auth\b)', l)), None)
    if at is None:
        raise Refused('%s has no auth lines - put the block in by hand' % path)
    lines[at:at] = pam_block(c).rstrip('\n').split('\n')
    _put_file(path, '\n'.join(lines), 0o644)
    return 'SSH asks for a code from otp (pam_radius)'


def sshd_text(c):
    lines = ['# otp - Settings -> SSH server and notices. Changed there, not here: this',
             '# file is written whole each time.',
             'Port %d' % c['port'],
             'PermitRootLogin %s' % c['permit_root'],
             'PasswordAuthentication %s' % ('yes' if c['password'] else 'no'),
             # A code from otp is asked in a second prompt: keyboard-interactive.
             'KbdInteractiveAuthentication %s' % ('yes' if c['password'] or c.get('radius')
                                                  else 'no'),
             'PubkeyAuthentication yes',
             'MaxAuthTries %d' % c['tries']]
    if c.get('radius'):
        lines.append('UsePAM yes')
    if c['allow_users']:
        lines.append('AllowUsers %s' % ' '.join(c['allow_users']))
    lines.append('Banner %s' % (notice_paths()['banner'] if c['notice_ssh'] else 'none'))
    lines += sshd_key_and_code(c)
    return '\n'.join(lines) + '\n'


def sshd_key_and_code(c):
    """A key first, then the code (1.0.183) - for the accounts the code is
    asked of; the others as before. A Match block, last in this file: sshd
    (8.2 and later) ends it at the end of the file it is in - checked after
    writing (sshd_match_kept)."""
    if not (c.get('radius') and c.get('radius_with_key')):
        return []
    both = 'AuthenticationMethods publickey,keyboard-interactive'
    out = []
    users = list(c.get('radius_users') or [])
    if sshd_root_code_key_only(c):
        # Root with a key only, and the code asked of it too (1.0.191): sshd hands
        # PAM "\b\n\r\177INCORRECT" for whatever root types where root may not use
        # a password - every code was refused. For root alone: what it types
        # reaches PAM, a key and the code both needed, never a password alone.
        out += ['# Root: a key, then the code from otp - never a password alone',
                'Match User root', '    PermitRootLogin yes', '    PasswordAuthentication no',
                '    ' + both]
        users = [u for u in users if u != 'root']
        if c.get('radius_users') and not users:
            return out
    if users:
        return out + ['# A key, then the code from otp - these accounts only',
                      'Match User %s' % ','.join(users), '    ' + both]
    if c.get('radius_root') and not out:
        return ['# A key, then the code from otp', both]
    return out + ['# A key, then the code from otp%s' % ('' if out else ' - root as before'),
                  'Match User *,!root', '    ' + both]


def sshd_root_code_key_only(c):
    """The code asked of root, root signing in with a key only, a key then the code."""
    if not (c.get('radius') and c.get('radius_with_key')) or c.get('permit_root') != 'prohibit-password':
        return False
    users = c.get('radius_users') or []
    return 'root' in users if users else bool(c.get('radius_root'))


def sshd_match_kept():
    """'' where every setting but AuthenticationMethods is the same for root
    and for anybody else - otp's Match did not reach into the system's own
    lines; else what differs."""
    def t(user):
        got = subprocess.run([SSHD_BIN, '-T', '-f', sshd_conf_path(), '-C',
                              'user=%s,host=localhost,addr=127.0.0.1' % user],
                             capture_output=True, text=True)
        return {l.split(' ', 1)[0]: l for l in got.stdout.split('\n') if l.strip()}, got.returncode
    a, ra = t('root')
    b, rb = t('otp-nobody-check')
    if ra or rb:
        return 'sshd -T did not answer'
    # Root's own block (1.0.191) sets these two for it, on purpose.
    ours = ('authenticationmethods', 'permitrootlogin', 'passwordauthentication')
    diff = sorted(k for k in set(a) | set(b) if k not in ours and a.get(k) != b.get(k))
    return ', '.join(diff[:5])


def sshd_selinux_port(port):
    """A port other than 22 let through by SELinux, where it is enforcing."""
    if port == 22 or not shutil.which('getenforce'):
        return ''
    mode = subprocess.run(['getenforce'], capture_output=True, text=True).stdout.strip()
    if mode != 'Enforcing':
        return ''
    if not shutil.which('semanage'):
        raise Refused('SELinux keeps sshd to port 22 and semanage is not on this machine '
                      '(dnf install policycoreutils-python-utils)')
    got = subprocess.run(['semanage', 'port', '-a', '-t', 'ssh_port_t', '-p', 'tcp', str(port)],
                         capture_output=True, text=True)
    # "already defined" is said for a port of another type too (1.0.248): 8080 is http_cache_port_t
    # - taken as done, sshd could not listen there after the reload, and SSH was down.
    if got.returncode != 0 and 'already defined' in (got.stderr or '') and \
            se_port_has(se_ports(), 'ssh_port_t', 'tcp', port):
        return 'SELinux lets sshd use port %d' % port
    if got.returncode != 0:
        got = subprocess.run(['semanage', 'port', '-m', '-t', 'ssh_port_t', '-p', 'tcp',
                              str(port)], capture_output=True, text=True)
        if got.returncode != 0:
            raise Refused('semanage: %s' % (got.stderr or got.stdout).strip()[-200:])
    return 'SELinux lets sshd use port %d' % port


def sshd_reload():
    if NO_SERVICES:
        return
    for unit in ('sshd', 'ssh'):
        got = subprocess.run(['systemctl', 'reload-or-restart', unit], capture_output=True,
                             text=True)
        if got.returncode == 0:
            return
    raise Refused('sshd could not be reloaded: %s' % (got.stderr or '').strip()[-200:])


def sshd_trial_read():
    try:
        return json.loads(_read_or(SSHD_STATE) or '{}')
    except ValueError:
        return {}


def sshd_put_back(why='not kept in time'):
    """What was there before the change on trial, back."""
    t = sshd_trial_read()
    if not t:
        return False
    drop = os.path.join(SSH_DIR, SSHD_DROPIN)
    if t.get('dropin') is None:
        _drop(drop)
    else:
        _put_file(drop, t['dropin'], 0o600)
    for where in ('issue', 'motd'):
        notice_set(where, None)
        if t.get(where) is not None:
            text = t[where]
            if where == 'issue':
                # Kept as the file had it - agetty's escaping in already (1.0.249): put in again
                # as it is, every backslash doubled at each trial not kept.
                text = text.rstrip('\n').replace('\\\\', '\\')
            notice_set(where, text)
    banner = notice_paths()['banner']
    if t.get('banner') is None:
        _drop(banner)
    else:
        _put_file(banner, t['banner'])
    if 'pam' in t:
        if t['pam'] is not None:
            _put_file(pam_sshd_path(), t['pam'], 0o644)
        if t.get('pamconf') is None:
            _drop(pam_radius_conf_path())
        else:
            _put_file(pam_radius_conf_path(), t['pamconf'], 0o600)
    try:
        sshd_reload()
    except Refused:
        pass
    _drop(SSHD_STATE)
    write_here('sshd-back.json', json.dumps({'at': time.time(), 'hash': t.get('hash'),
                                             'why': why}))
    return True


def sshd_arm(minutes, ident):
    """The timer that puts it back: systemd's own, not this helper's."""
    if NO_SERVICES or not minutes:
        return ''
    unit = 'otp-sshd-back-%s' % ident
    me = os.path.abspath(__file__)
    run(['systemd-run', '--on-active=%ds' % (int(minutes) * 60), '--unit', unit,
         sys.executable, '-I', me, '--sshd-back'], 'systemd-run')
    return unit


def sshd_disarm(t):
    unit = (t or {}).get('unit')
    if unit and not NO_SERVICES:
        subprocess.run(['systemctl', 'stop', unit + '.timer'], capture_output=True)


def sshd_apply_files(c, r, drop, now_dropin, paths, before):
    """The files of one change put in and sshd reloaded - what sshd_do undoes
    whole when anything of it fails (1.0.209)."""
    said = []
    if c['manage']:
        text = sshd_text(c)
        if c['notice_ssh']:
            _put_file(paths['banner'], c['notice'].rstrip() + '\n')
        _put_file(drop, text, 0o600)
        got = subprocess.run([SSHD_BIN, '-t', '-f', sshd_conf_path()], capture_output=True,
                             text=True)
        if got.returncode != 0:
            if now_dropin is None:
                _drop(drop)
            else:
                _put_file(drop, now_dropin, 0o600)
            raise Refused('sshd does not take it, so it is as it was: %s'
                          % (got.stderr or got.stdout).strip()[-300:])
        if c.get('radius_with_key'):
            drift = sshd_match_kept()
            if drift:
                if now_dropin is None:
                    _drop(drop)
                else:
                    _put_file(drop, now_dropin, 0o600)
                raise Refused('this sshd lets a Match of a file it includes reach its own '
                              'settings (%s) - a key and the code cannot be set here; it is '
                              'as it was' % drift)
        s = sshd_selinux_port(c['port'])
        if s:
            said.append(s)
        try:
            w = pam_set(c, r.get('radius_secret'), r.get('radius_port'))
        except Refused:
            if now_dropin is None:
                _drop(drop)
            else:
                _put_file(drop, now_dropin, 0o600)
            raise
        if w:
            said.append(w)
    else:
        if before['dropin'] is not None or os.path.exists(drop):
            _drop(drop)
        pam_set({'radius': False}, '', 0)
    notice_set('issue', c['notice'] if c['notice_console'] else None)
    notice_set('motd', c['notice'] if c['notice_motd'] else None)
    if not (c['manage'] and c['notice_ssh']):
        _drop(paths['banner'])
    sshd_reload()
    return said


def sshd_do(r):
    do = r.get('do')
    if do == 'apply':
        c = sshd_checked(r.get('conf'))
        trial = max(0, min(60, int(r.get('trial_min') or 0)))
        keys = root_keys_count()
        if c['manage']:
            if not sshd_reads_dropins():
                raise Refused('this sshd does not read sshd_config.d (OpenSSH before 8.2, or an '
                              'Include taken out of %s) - set it there by hand' % sshd_conf_path())
            if c['permit_root'] != 'no' and not c['password'] and not keys and \
                    not r.get('no_keys_ok'):
                raise Refused('root has no SSH key here, and passwords would be off: nobody would '
                              'reach this machine as root over SSH - add a key first')
            if c['permit_root'] == 'prohibit-password' and not keys and not r.get('no_keys_ok'):
                raise Refused('root may sign in only with a key and has none here - add a key '
                              'first')
        old = sshd_trial_read()
        # A change on trial changed again: one timer, the first state - its timer
        # stopped only once the new change is in (1.0.205). Stopped before it,
        # a change sshd refused left the one on trial with nothing to put it back.
        drop = os.path.join(SSH_DIR, SSHD_DROPIN)
        now_dropin = _read_or(drop)     # what this change, refused, goes back to
        paths = notice_paths()
        before = old or {'dropin': _read_or(drop), 'banner': _read_or(paths['banner']),
                         'issue': None, 'motd': None, 'pam': _read_or(pam_sshd_path()),
                         'pamconf': _read_or(pam_radius_conf_path())}
        if not old:
            for where in ('issue', 'motd'):
                cur = _read_or(paths[where])
                whole = os.path.basename(paths[where]) in ('issue', 'motd')
                if cur is not None and (not whole or cur.startswith(NOTICE_MARK.strip())):
                    before[where] = cur.split('\n', 1)[1] if whole else cur
        # Every file as it is now, put back on any failure (1.0.209): only sshd's
        # refusal was undone - a package that did not install, a notice that could
        # not be written or a reload that failed left the drop-in and PAM changed,
        # with no trial and no timer to put them back.
        entry = {pth: _read_or(pth) for pth in (drop, paths['banner'], paths['issue'],
                                                paths['motd'], pam_sshd_path(),
                                                pam_radius_conf_path())}
        ident = re.sub(r'[^A-Za-z0-9]', '', str(r.get('id') or ''))[:12] or 'x'
        new_unit = ''
        try:
            # The timer that puts it back armed first (1.0.234): armed after the change, a
            # timer that could not be made left the change in with nothing to undo it - and
            # the one before already stopped.
            if trial and c['manage']:
                new_unit = sshd_arm(trial, ident)
                _put_file(SSHD_STATE, json.dumps(dict(
                    before, hash=str(r.get('hash') or '')[:64], until=time.time() + trial * 60,
                    unit=new_unit)), 0o600)
            said = sshd_apply_files(c, r, drop, now_dropin, paths, before)
        except BaseException:
            for pth, was in entry.items():
                try:
                    if was is None:
                        _drop(pth)
                    else:
                        _put_file(pth, was, 0o600 if pth in (drop, pam_radius_conf_path())
                                  else 0o644)
                except Exception:                       # noqa: BLE001
                    pass
            try:
                sshd_reload()
            except Exception:                           # noqa: BLE001
                pass
            if new_unit:
                sshd_disarm({'unit': new_unit})
            try:
                if old:
                    _put_file(SSHD_STATE, json.dumps(old), 0o600)
                else:
                    _drop(SSHD_STATE)
            except Exception:                           # noqa: BLE001
                pass
            raise
        if old and old.get('unit') != new_unit:
            sshd_disarm(old)
        if not (trial and c['manage']):
            _drop(SSHD_STATE)
        said.append('sshd reloaded')
    elif do == 'keep':
        t = sshd_trial_read()
        if t:
            sshd_disarm(t)
            _drop(SSHD_STATE)
    elif do == 'back':
        sshd_put_back(str(r.get('why') or 'asked to go back'))
    elif do == 'pamconf':
        # The gate's secret and port, nothing else (1.0.181): only where our
        # block is in sshd's PAM.
        text = _read_or(pam_sshd_path()) or ''
        if PAM_BEGIN in text:
            pam_radius_conf_write(r.get('radius_secret'), r.get('radius_port'))
            # A block from before 1.0.188: skip_passwd put in its pam_radius line.
            fixed = pam_skip_passwd(text)
            if fixed != text:
                _put_file(pam_sshd_path(), fixed, 0o644)
    elif do != 'read':
        raise Refused('read, apply, keep, back or pamconf')
    v = sshd_values()
    t = sshd_trial_read()
    return {'values': v, 'there': os.path.exists(SSHD_BIN), 'dropins': sshd_reads_dropins(),
            'dropin': _read_or(os.path.join(SSH_DIR, SSHD_DROPIN)), 'keys': root_keys_count(),
            'trial': {'hash': t.get('hash'), 'until': t.get('until')} if t else {},
            'paths': notice_paths(),
            'radius': {'module': bool(pam_radius_module()),
                       'pam': PAM_BEGIN in (_read_or(pam_sshd_path()) or ''),
                       'skip_passwd': pam_skip_passwd(_read_or(pam_sshd_path()) or '') ==
                       (_read_or(pam_sshd_path()) or ''),
                       'conf': os.path.exists(pam_radius_conf_path()),
                       'fp': pam_radius_conf_fp()},
            'selinux': subprocess.run(['getenforce'], capture_output=True, text=True).stdout.strip()
            if shutil.which('getenforce') else ''}


def sshd_part():
    d = web_fd()
    try:
        raw = read_req(SSHD_ASK, 65536)
    except FileNotFoundError:
        return
    except (Refused, OSError):
        drop_ask(SSHD_ASK, d)
        return
    drop_ask(SSHD_ASK, d)
    out = {'at': time.time(), 'ok': False, 'id': ''}
    try:
        r = json.loads(raw.decode('utf-8'))
        if not isinstance(r, dict):
            raise Refused('the request is not an object')
        out['id'] = re.sub(r'[^A-Za-z0-9]', '', str(r.get('id') or ''))[:40]
        out['data'] = sshd_do(r)
        out['ok'] = True
    except Refused as e:
        out['said'] = str(e)[:400]
    except Exception as e:                              # noqa: BLE001
        out['said'] = 'it went wrong: %s' % str(e)[:300]
    write_here(SSHD_FILE, json.dumps(out))


# ---- the journal and the logs (1.0.166) ------------------------------------------------
# Asked with logs.ask by the daemon of this node: how much systemd's journal
# may take and for how long (journald.conf.d/00-otp.conf, journald restarted
# only when that file changed), and how many files of /var/log/otp logrotate
# keeps and how big one may grow (/etc/logrotate.d/otp, the two lines only).
# Answered with what the journal takes now.
LOGS_ASK, LOGS_ANS = 'logs.ask', 'logs.ans'
JOURNAL_DROPIN = 'systemd/journald.conf.d/00-otp.conf'
LOGROTATE_OTP = 'logrotate.d/otp'


def _int_in(r, key, lo, hi):
    try:
        v = int(r.get(key) or 0)
    except (TypeError, ValueError):
        raise Refused('%s: a whole number' % key)
    if not lo <= v <= hi:
        raise Refused('%s: %d to %d' % (key, lo, hi))
    return v


def journal_use():
    if not shutil.which('journalctl'):
        return None
    try:
        got = subprocess.run(['journalctl', '--disk-usage'], capture_output=True, text=True,
                             timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r'take up ([0-9.]+)([BKMGT])', got.stdout + got.stderr)
    if not m:
        return None
    return int(float(m.group(1)) * {'B': 1, 'K': 1 << 10, 'M': 1 << 20, 'G': 1 << 30,
                                    'T': 1 << 40}[m.group(2)])


def logs_do(r):
    mb = _int_in(r, 'journal_mb', 0, 100000)
    days = _int_in(r, 'journal_days', 0, 3650)
    keep = _int_in(r, 'keep', 1, 3650)
    max_mb = _int_in(r, 'max_mb', 1, 100000)
    said = []
    path = os.path.join(ETC_DIR, JOURNAL_DROPIN)
    before = _read_or(path)
    if mb or days:
        text = ('# Written by otp (Settings - Disks and logs); changed there, not here.\n'
                '[Journal]\n' + ('SystemMaxUse=%dM\n' % mb if mb else '') +
                ('MaxRetentionSec=%dday\n' % days if days else ''))
        if before != text:
            _put_file(path, text)
            said.append('the journal: %s' % ', '.join(
                ([('at most %d MB' % mb)] if mb else []) + ([('%d days' % days)] if days else [])))
    elif before is not None:
        _drop(path)
        said.append('the journal: as the system has it')
    changed = (_read_or(path) != before)
    if changed and not NO_SERVICES and shutil.which('systemctl'):
        got = subprocess.run(['systemctl', 'restart', 'systemd-journald'], capture_output=True,
                             text=True, timeout=60)
        if got.returncode != 0:
            said.append('systemd-journald did not restart: %s' % (got.stderr or '').strip()[-200:])
    lr = os.path.join(ETC_DIR, LOGROTATE_OTP)
    text = _read_or(lr)
    if text is None:
        said.append('%s is not there - otp\'s logs are not rotated' % lr)
    else:
        new = re.sub(r'(?m)^(\s*)rotate\s+\d+\s*$', r'\g<1>rotate %d' % keep, text)
        new = re.sub(r'(?m)^(\s*)maxsize\s+\d+[kMG]?\s*$', r'\g<1>maxsize %dM' % max_mb, new)
        if new != text:
            _put_file(lr, new)
            said.append('otp\'s logs: %d kept, %d MB each at most' % (keep, max_mb))
    return {'journal_use': journal_use(), 'journal_conf': _read_or(path) or '',
            'rotate_conf': '\n'.join(x.strip() for x in (_read_or(lr) or '').splitlines()
                                     if re.match(r'\s*(rotate|maxsize)\b', x)),
            'said': said}


def logs_part():
    d = web_fd()
    try:
        raw = read_req(LOGS_ASK, 4096)
    except FileNotFoundError:
        return
    except (Refused, OSError):
        drop_ask(LOGS_ASK, d)
        return
    drop_ask(LOGS_ASK, d)
    out = {'at': time.time(), 'ok': False, 'id': ''}
    try:
        r = json.loads(raw.decode('utf-8'))
        if not isinstance(r, dict) or r.get('do') != 'apply':
            raise Refused('apply only')
        out['id'] = re.sub(r'[^A-Za-z0-9]', '', str(r.get('id') or ''))[:40]
        out['data'] = logs_do(r)
        out['ok'] = True
    except Refused as e:
        out['said'] = str(e)[:400]
    except Exception as e:                              # noqa: BLE001
        out['said'] = 'it went wrong: %s' % str(e)[:300]
    write_here(LOGS_ANS, json.dumps(out))


# ---- updates of the operating system (1.0.158) ------------------------------------------
# Asked with osup.ask, answered at once; the work itself - minutes of dnf or
# apt - runs as a unit of its own (systemd-run), so this oneshot service ends
# and the other asks are served meanwhile. Its progress and its last lines go
# into osup.json, every second or so.
OSUP_ASK = 'osup.ask'
OSUP_ANS = 'osup.ans'
OSUP_FILE = 'osup.json'
OSUP_LOCK = os.environ.get('OTP_OSUP_LOCK', '/run/otp-osup.lock')
OSUP_PM = os.environ.get('OTP_OSUP_PM', '')          # tests: a fake package manager
# The proxy dnf and apt go through (1.0.166): handed over in osup.ask, kept
# here for the job, readable by root only, never on a command line.
OSUP_PROXY = os.environ.get('OTP_OSUP_PROXY', '/run/otp-osup-proxy.json')


def osup_proxy_keep(r):
    url = str(r.get('proxy') or '').strip()
    if url and not re.match(r'^https?://[^\s]+\Z', url):
        raise Refused('the proxy is not an http:// address')
    no = ','.join(w for w in re.split(r'[\s,;]+', re.sub(r'[^A-Za-z0-9.*:/\[\],;\s_-]', '',
                                                          str(r.get('proxy_no') or ''))) if w)
    if not url:
        _drop(OSUP_PROXY)
        return
    fd = os.open(OSUP_PROXY + '.new', os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                 0o600)
    with os.fdopen(fd, 'w') as f:
        os.fchmod(f.fileno(), 0o600)
        f.write(json.dumps({'url': url, 'no': no}))
    os.replace(OSUP_PROXY + '.new', OSUP_PROXY)


def osup_proxy_env(env):
    try:
        got = json.loads(_read_or(OSUP_PROXY) or '{}')
    except ValueError:
        got = {}
    if got.get('url'):
        for k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
            env[k] = got['url']
        if got.get('no'):
            env['no_proxy'] = env['NO_PROXY'] = got['no']
    return env


def osup_pm():
    if OSUP_PM:
        return 'fake'
    if shutil.which('dnf'):
        return 'dnf'
    if shutil.which('apt-get'):
        return 'apt'
    return ''


def osup_running():
    import fcntl
    try:
        fd = os.open(OSUP_LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    except OSError:
        return True
    finally:
        os.close(fd)


def osup_launch(ident, kind, security=False):
    if osup_running():
        raise Refused('an update or a look for updates is going on already')
    if not osup_pm():
        raise Refused('neither dnf nor apt-get is on this machine')
    me = os.path.abspath(__file__)
    argv = [sys.executable, '-I', me, '--os-job', ident, kind] + (['security'] if security else [])
    if (shutil.which('systemd-run') and not NO_SERVICES and os.path.isdir('/run/systemd/system')):
        got = subprocess.run(['systemd-run', '--unit', 'otp-os-%s-%s' % (kind, ident[:12]),
                              '--collect', '--quiet', '--property', 'TimeoutStopSec=30min'] + argv,
                             capture_output=True, text=True, timeout=30)
        if got.returncode != 0:
            raise Refused('systemd-run: %s' % (got.stderr or got.stdout).strip()[-200:])
        return
    subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)


def osup_part():
    d = web_fd()
    try:
        raw = read_req(OSUP_ASK, 4096)
    except FileNotFoundError:
        return
    except (Refused, OSError):
        drop_ask(OSUP_ASK, d)
        return
    drop_ask(OSUP_ASK, d)
    out = {'at': time.time(), 'ok': False, 'id': ''}
    try:
        r = json.loads(raw.decode('utf-8'))
        if not isinstance(r, dict):
            raise Refused('the request is not an object')
        out['id'] = re.sub(r'[^A-Za-z0-9]', '', str(r.get('id') or ''))[:40]
        kind = r.get('kind')
        if r.get('do') != 'run' or kind not in ('check', 'upgrade'):
            raise Refused('run: check or upgrade')
        osup_proxy_keep(r)
        osup_launch(out['id'], kind, bool(r.get('security')) and kind == 'upgrade')
        out['ok'] = True
        out['data'] = {'started': kind, 'pm': osup_pm(), 'security': bool(r.get('security'))}
    except Refused as e:
        out['said'] = str(e)[:400]
    except Exception as e:                              # noqa: BLE001
        out['said'] = 'it went wrong: %s' % str(e)[:300]
    write_here(OSUP_ANS, json.dumps(out))


# The packages a restart is needed for once they are updated, as dnf
# needs-restarting -r and Debian's reboot-required name them (1.0.159).
REBOOT_PKGS = {'kernel', 'kernel-core', 'kernel-rt', 'kernel-rt-core', 'kernel-modules',
               'kernel-uek', 'glibc', 'linux-firmware', 'systemd', 'dbus', 'dbus-broker',
               'dbus-daemon', 'microcode_ctl', 'zlib', 'zlib-ng-compat', 'libc6', 'linux-base',
               'intel-microcode', 'amd64-microcode'}


def reboot_for(packages):
    """Which of the packages waiting want a restart once updated."""
    out = []
    for p in packages:
        name = str(p).split()[0] if str(p).split() else ''
        if re.search(r'\.(x86_64|aarch64|noarch|i686|ppc64le|s390x)$', name):
            name = name.rsplit('.', 1)[0]
        if name in REBOOT_PKGS or name.startswith(('linux-image', 'kernel-core-', 'linux-modules')):
            out.append(name)
    return sorted(set(out))


def reboot_now(pm, env, say=None):
    """Whether this machine waits for a restart already."""
    if pm == 'fake':
        return subprocess.run([OSUP_PM, 'needs-restart'], stdout=subprocess.DEVNULL).returncode == 1
    if pm == 'dnf':
        nr = subprocess.run(['dnf', 'needs-restarting', '-r'], capture_output=True,
                            text=True, env=env, timeout=300)
        if nr.returncode == 1 and say:
            say(nr.stdout.strip().splitlines()[0] if nr.stdout.strip() else 'a restart is needed')
        return nr.returncode == 1
    return os.path.exists('/var/run/reboot-required')


def osup_job(ident, kind, security=False):
    """The work itself, as root, in a process of its own."""
    import fcntl
    fd = os.open(OSUP_LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 1
    state = {'id': ident, 'kind': kind, 'state': 'running', 'pct': 1, 'lines': [],
             'began': time.time(), 'at': time.time(), 'packages': [], 'reboot': False,
             'pm': osup_pm(), 'phase': 'starting'}
    last = [0.0]

    def put(force=False):
        state['at'] = time.time()
        if force or time.time() - last[0] > 0.8:
            last[0] = time.time()
            state['lines'] = state['lines'][-400:]
            try:
                write_here(OSUP_FILE, json.dumps(state))
            except OSError:
                pass        # best effort (1.0.249): one failed write ended the job mid-transaction

    def say(line):
        line = line.rstrip()
        if line:
            state['lines'].append(line[:300])
        put()

    env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'LC_ALL': 'C',
           'DEBIAN_FRONTEND': 'noninteractive', 'HOME': '/root'}
    osup_proxy_env(env)

    def stream(cmd, on_line=None, ok=(0,)):
        say('$ ' + ' '.join(cmd))
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                             stdin=subprocess.DEVNULL, text=True, bufsize=1)
        try:
            for ln in p.stdout:
                say(ln)
                if on_line:
                    on_line(ln)
        finally:
            try:
                for _ in p.stdout:      # read to its end: a full pipe never let it finish
                    pass
            except Exception:           # noqa: BLE001
                pass
            rc = p.wait()       # never left running behind (1.0.249)
        if rc not in ok:
            raise Refused('%s ended with %d' % (cmd[0], rc))
        return rc

    pm = state['pm']
    try:
        put(True)
        if kind == 'check':
            state['phase'] = 'asking for what is new'
            pk = []
            if pm == 'fake':
                stream([OSUP_PM, 'check'], lambda ln: pk.append(ln.strip())
                       if ln.strip() and not ln.startswith('#') else None)
            elif pm == 'dnf':
                rc_out = []
                stream(['dnf', '-q', '--refresh', 'check-update'], rc_out.append, ok=(0, 100))
                for ln in rc_out:
                    parts = ln.split()
                    if len(parts) >= 3 and '.' in parts[0] and not ln.startswith(' '):
                        pk.append('%s %s' % (parts[0], parts[1]))
                state['security'] = 0
                sec = subprocess.run(['dnf', '-q', 'updateinfo', 'list', '--security'],
                                     capture_output=True, text=True, env=env, timeout=300)
                state['security'] = len([x for x in sec.stdout.splitlines() if x.strip()])
            else:
                stream(['apt-get', 'update'])
                got = subprocess.run(['apt', 'list', '--upgradable'], capture_output=True,
                                     text=True, env=env, timeout=300)
                for ln in got.stdout.splitlines():
                    if '/' in ln and '[upgradable' in ln:
                        name = ln.split('/', 1)[0]
                        ver = ln.split()[1] if len(ln.split()) > 1 else ''
                        pk.append('%s %s' % (name, ver))
            state['packages'] = pk[:1000]
            state['count'] = len(pk)
            # Whether the update will need a restart, told before it is made.
            state['phase'] = 'whether a restart is needed'
            state['reboot_why'] = reboot_for(pk)
            state['reboot_after'] = bool(state['reboot_why'])
            try:
                state['reboot_now'] = reboot_now(pm, env)
            except (OSError, subprocess.SubprocessError):
                state['reboot_now'] = False
            if state['reboot_now']:
                say('a restart is needed already, before any update')
            if state['reboot_why']:
                say('a restart will be needed after the update: %s' % ', '.join(state['reboot_why']))
            state['pct'] = 100
        else:
            seen = {'total': 0, 'done': 0}

            def count(ln):
                m = re.search(r'\b(\d+)/(\d+)\s*$', ln)
                if pm in ('dnf', 'fake') and m and re.search(
                        r'(Upgrading|Installing|Cleanup|Verifying|Running scriptlet|Erasing|'
                        r'Reinstalling|Downgrading|Obsoleting)\s*:', ln):
                    total = int(m.group(2)) * 2          # each one upgraded and then verified
                    seen['total'] = max(seen['total'], total)
                    seen['done'] = min(seen['total'], seen['done'] + 1)
                    state['phase'] = 'putting the packages in'
                if pm == 'dnf' and ln.startswith('Downloading Packages'):
                    state['phase'] = 'downloading'
                    state['pct'] = max(state['pct'], 8)
                if pm == 'apt':
                    m2 = re.match(r'^(\d+) upgraded, (\d+) newly installed', ln)
                    if m2:
                        seen['total'] = (int(m2.group(1)) + int(m2.group(2))) * 2
                    if ln.startswith(('Unpacking ', 'Setting up ')):
                        seen['done'] += 1
                        state['phase'] = 'putting the packages in'
                    if ln.startswith('Get:'):
                        state['phase'] = 'downloading'
                        state['pct'] = max(state['pct'], 8)
                if seen['total']:
                    state['pct'] = max(state['pct'], min(97, 10 + int(87 * seen['done'] /
                                                                      seen['total'])))
            state['phase'] = 'asking for what is new'
            # Only the security updates where asked (1.0.164): dnf's own
            # --security, unattended-upgrade on apt (it takes the security
            # sources only, as Debian and Ubuntu set it up).
            state['security_only'] = bool(security)
            if pm == 'fake':
                stream([OSUP_PM, 'upgrade'] + (['security'] if security else []), count)
            elif pm == 'dnf':
                stream(['dnf', '-y', '--refresh', 'upgrade'] + (['--security'] if security else []),
                       count)
            elif security:
                if not shutil.which('unattended-upgrade'):
                    raise Refused('only the security updates: unattended-upgrade is not on this '
                                  'machine (apt install unattended-upgrades)')
                stream(['apt-get', 'update'])
                state['pct'] = max(state['pct'], 5)
                stream(['unattended-upgrade', '-v'], count)
            else:
                stream(['apt-get', 'update'])
                state['pct'] = max(state['pct'], 5)
                stream(['apt-get', '-y', '-o', 'Dpkg::Options::=--force-confdef', '-o',
                        'Dpkg::Options::=--force-confold', 'upgrade'], count)
            state['phase'] = 'whether a restart is needed'
            state['reboot'] = reboot_now(pm, env, say)
            state['pct'] = 100
        state['state'] = 'done'
        state['phase'] = 'done'
    except Refused as e:
        state.update(state='failed', said=str(e)[:300])
    except Exception as e:                              # noqa: BLE001
        state.update(state='failed', said='it broke: %s' % str(e)[:300])
    finally:
        put(True)
        os.close(fd)
    return 0


# ---- SELinux (1.0.233) -------------------------------------------------------------------
# Asked in selinux.ask by the daemon of this node, from the pages (Settings - High security)
# or `otp --selinux-check`: how it is - the mode, otp's module, the labels otp's files have,
# the booleans and ports otp needs, what SELinux refused since the machine started - and,
# when asked, the three steps: made ready and permissive, enforcing, permissive again.
# Nothing of it is done unless asked; a machine with SELinux disabled stays so.
SELINUX_ASK, SELINUX_FILE = 'selinux.ask', 'selinux.json'
SE_CONFIG = os.environ.get('OTP_SELINUX_CONFIG', '/etc/selinux/config')
SE_RELABEL = os.environ.get('OTP_SELINUX_RELABEL', '/.autorelabel')
SE_CMDLINE = os.environ.get('OTP_SELINUX_CMDLINE', '/proc/cmdline')
SE_MODULE = 'otp_server'
SE_CIL = os.environ.get('OTP_SELINUX_CIL', '/usr/local/lib/otp/otp_server.cil')
# What otp's files should be labelled; the label is the third field of the context.
SE_LABELS = (('/run/otp', 'httpd_var_run_t', 'the folder of the API token'),
             ('/run/otp/api-token', 'httpd_var_run_t', 'the API token the pages read'),
             ('/var/www/otp', 'httpd_sys_content_t', 'the pages'),
             ('/usr/libexec/keepalived/otp-vip-check', 'keepalived_unconfined_script_exec_t',
              'keepalived\'s check of this node'))
SE_BOOLEANS = ('httpd_can_network_connect', 'authlogin_radius')
SE_PORT_TYPES = ('radius_port_t', 'postgresql_port_t', 'ssh_port_t', 'http_port_t')
# The programs whose refusals are otp's business.
SE_DOMAINS = ('httpd_t', 'keepalived_t', 'keepalived_unconfined_script_t', 'sshd_t',
              'chronyd_t', 'postgresql_t', 'syslogd_t', 'logrotate_t', 'unconfined_service_t',
              'init_t')


SE_APPLIED = 'selinux-applied'      # when otp's needs were last put in (1.0.234)


def _se_run(cmd, timeout=120, light=False, data=None):
    if not shutil.which(cmd[0]):
        return None
    if light:
        # The heavy ones (semanage loads the whole policy, ausearch reads the audit log since
        # the start) at the lowest priority (1.0.234): run on every node every half hour, they
        # took a core for seconds beside RADIUS.
        if shutil.which('ionice'):
            cmd = ['ionice', '-c', '3'] + cmd
        if shutil.which('nice'):
            cmd = ['nice', '-n', '19'] + cmd
    try:
        return subprocess.run(cmd, input=data, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def se_applied_at():
    # In root's own folder (1.0.248): in the service's, a time ahead written there hid every
    # refusal of SELinux from the check before enforcing.
    try:
        fd = os.open(os.path.join(ROOT_STATE_DIR, SE_APPLIED), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as f:
            return float((json.load(f) or {}).get('at') or 0)
    except (OSError, TypeError, ValueError, AttributeError):
        return 0.0


SE_UPGRADE_BOOT = 'selinux-upgrade-boot'


def se_upgrade_boot_same():
    """Whether the machine has not started again since the upgrade that lost the note of when
    otp's needs were put in (1.0.249): after a restart what is counted since then is new."""
    try:
        now = open('/proc/sys/kernel/random/boot_id').read().strip()
    except OSError:
        return False
    try:
        fd = os.open(os.path.join(ROOT_STATE_DIR, SE_UPGRADE_BOOT), os.O_RDONLY | os.O_NOFOLLOW |
                     os.O_NONBLOCK)
        with os.fdopen(fd) as f:
            was = f.read(100).strip()
    except OSError:
        try:
            root_state_write(SE_UPGRADE_BOOT, now + '\n')
        except OSError:
            pass
        return True
    return was == now


def root_state_write(name, text):
    os.makedirs(ROOT_STATE_DIR, mode=0o700, exist_ok=True)
    os.chmod(ROOT_STATE_DIR, 0o700)
    write_root(os.path.join(ROOT_STATE_DIR, name), text, 0o600)


def se_auditd():
    """Whether what SELinux refuses is written down at all: auditd running."""
    fake = os.environ.get('OTP_SELINUX_AUDITD')            # tests
    if fake:
        return fake == 'active'
    got = _se_run(['systemctl', 'is-active', 'auditd'], 20)
    return got is None or (got.stdout or '').strip() == 'active'


def se_mode():
    got = _se_run(['getenforce'], 20)
    if got is None:
        return 'absent'                 # no SELinux on this machine at all (Debian, Ubuntu)
    return (got.stdout or '').strip() or 'Disabled'


def se_config():
    text = _read_or(SE_CONFIG) or ''
    out = {}
    for line in text.splitlines():
        m = re.match(r'^\s*(SELINUX|SELINUXTYPE)\s*=\s*([A-Za-z0-9_-]+)\s*$', line)
        if m:
            out[m.group(1)] = m.group(2)
    return {'mode': out.get('SELINUX', ''), 'type': out.get('SELINUXTYPE', ''),
            'there': bool(text)}


def se_config_set(mode):
    """SELINUX= in /etc/selinux/config, the rest of the file as it is."""
    if mode not in ('permissive', 'enforcing'):
        raise Refused('permissive or enforcing')
    text = _read_or(SE_CONFIG)
    if text is None:
        raise Refused('%s is not there - is the SELinux policy installed? '
                      '(dnf install selinux-policy-targeted)' % SE_CONFIG)
    if re.search(r'(?m)^\s*SELINUX\s*=', text):
        new = re.sub(r'(?m)^(\s*)SELINUX\s*=.*$', r'\g<1>SELINUX=%s' % mode, text)
    else:
        new = text.rstrip('\n') + '\nSELINUX=%s\n' % mode
    if new != text:
        _put_file(SE_CONFIG, new)


def se_cmdline_off():
    """selinux=0 on the kernel's command line: the config alone does not switch it on."""
    return bool(re.search(r'(?:^|\s)selinux=0(?:\s|$)', _read_or(SE_CMDLINE) or ''))


def se_label(path):
    fake = os.environ.get('OTP_SELINUX_LABELS')         # tests: {path: label}
    if fake:
        try:
            return (json.load(open(fake)) or {}).get(path)
        except (OSError, ValueError):
            return None
    try:
        raw = os.getxattr(path, 'security.selinux', follow_symlinks=False)
    except (OSError, AttributeError):
        return None
    ctx = raw.decode('utf-8', 'replace').rstrip('\0')
    parts = ctx.split(':')
    return parts[2] if len(parts) >= 3 else None


def se_module_in():
    got = _se_run(['semodule', '-l'], 120, light=True)
    if got is None or got.returncode != 0:
        return None
    return any(line.split()[:1] == [SE_MODULE] for line in got.stdout.splitlines())


def se_bool(name):
    got = _se_run(['getsebool', name], 20)
    if got is None or got.returncode != 0:
        return None
    return bool(re.search(r'-->\s*on\s*$', got.stdout.strip()))


def se_ports():
    """semanage port -l: {(type, proto): [(lo, hi), ...]}; None without semanage."""
    got = _se_run(['semanage', 'port', '-l'], 120, light=True)
    if got is None or got.returncode != 0:
        return None
    out = {}
    for line in got.stdout.splitlines():
        m = re.match(r'^(\S+_port_t)\s+(tcp|udp|sctp|dccp)\s+(.+)$', line.strip())
        if not m:
            continue
        spans = []
        for p in m.group(3).split(','):
            p = p.strip()
            a, _, b = p.partition('-')
            try:
                spans.append((int(a), int(b or a)))
            except ValueError:
                continue
        out.setdefault((m.group(1), m.group(2)), []).extend(spans)
    return out


def se_port_has(ports, kind, proto, port):
    return any(lo <= port <= hi for lo, hi in (ports or {}).get((kind, proto), []))


def se_denials(since=0.0):
    """What SELinux refused since the machine started - or since otp's needs were last put
    in (1.0.234: what was refused before that is what they put right) - for the programs otp
    works with."""
    got = _se_run(['ausearch', '-m', 'AVC,USER_AVC', '-ts', 'boot'], 120, light=True)
    if got is None:
        return {'tool': False, 'total': 0, 'groups': [], 'since': since}
    groups = {}
    lines = {}
    total = 0
    for line in (got.stdout or '').splitlines():
        if 'avc:' not in line or 'denied' not in line:
            continue
        when = re.search(r'msg=audit\((\d+)(?:\.\d+)?:', line)
        if since and when and int(when.group(1)) < since:
            continue
        perms = re.search(r'denied\s+\{([^}]*)\}', line)
        sc = re.search(r'scontext=(\S+)', line)
        tc = re.search(r'tcontext=(\S+)', line)
        cl = re.search(r'tclass=(\S+)', line)
        comm = re.search(r'comm=(\S+)', line)
        name = re.search(r'\bname=(\S+)', line)
        if not (perms and sc and tc and cl):
            continue
        st = (sc.group(1).split(':') + ['', '', ''])[2]
        tt = (tc.group(1).split(':') + ['', '', ''])[2]
        what = ' '.join(x for x in (comm.group(1) if comm else '', name.group(1) if name else '')
                        if x)
        if st not in SE_DOMAINS and 'otp' not in line:
            continue
        total += 1
        key = (st, tt, cl.group(1), perms.group(1).strip())
        lines[key] = line
        g = groups.setdefault(key, {'source': st, 'target': tt, 'class': cl.group(1),
                                    'perms': perms.group(1).strip(), 'count': 0, 'what': ''})
        g['count'] += 1
        g['what'] = what.replace('"', '')[:120] or g['what']
        g['permissive'] = 'permissive=1' in line
    # Refused once, allowed now (1.0.238): a module or a boolean that came after it - an upgrade
    # with a newer otp_server - settles it without "Put in what otp needs" pressed again.
    settled = 0
    for key in se_allowed_now(lines):
        settled += groups[key]['count']
        total -= groups.pop(key)['count']
    out = sorted(groups.values(), key=lambda g: -g['count'])[:30]
    return {'tool': True, 'total': total, 'groups': out, 'since': since, 'settled': settled}


def se_allowed_now(lines):
    """Which of the refusals (one line for each kind) the policy loaded now allows, as audit2why
    tells: "would be allowed by active policy". Nothing when audit2why is not there, or says
    nothing plain - then they count, as until now."""
    if not lines:
        return []
    by_id = {}
    for key, line in lines.items():
        m = re.search(r'msg=audit\(([0-9.]+:\d+)\)', line)
        if m:
            by_id[m.group(1)] = key
    if not by_id:
        return []
    got = _se_run(['audit2why'], 300, light=True,
                  data=''.join(lines[k] + '\n' for k in by_id.values()))
    if got is None or got.returncode != 0:
        return []
    now = set()
    cur = None
    for line in (got.stdout or '').splitlines():
        m = re.search(r'msg=audit\(([0-9.]+:\d+)\)', line)
        if m and 'avc:' in line:
            cur = by_id.get(m.group(1))
            continue
        if cur is not None and 'would be allowed by active policy' in line:
            now.add(cur)
    return sorted(now)


def se_want_checked(r, left_out=None):
    """What the daemon says otp needs here: booleans and ports, checked against what may be.
    left_out (1.0.262): a list a port of a type this helper does not set is said in and left
    out - a newer daemon's need refused the whole request, the booleans and the other ports too."""
    bools = []
    for b in (r.get('booleans') or [])[:8]:
        if not isinstance(b, dict) or b.get('name') not in SE_BOOLEANS:
            raise Refused('a boolean otp does not set')
        bools.append({'name': b['name'], 'why': str(b.get('why') or '')[:120]})
    ports = []
    for p in (r.get('ports') or [])[:16]:
        if left_out is not None and isinstance(p, dict) and p.get('proto') in ('tcp', 'udp') and \
                p.get('type') not in SE_PORT_TYPES and \
                re.match(r'^[a-z][a-z0-9_]{0,40}_port_t\Z', str(p.get('type') or '')):
            left_out.append('port %s/%s (%s) left out: this helper does not set %s - install.sh of '
                            'the daemon\'s version puts in one that does'
                            % (str(p.get('port'))[:6], p['proto'], str(p.get('why') or '')[:80],
                               p['type']))
            continue
        if not isinstance(p, dict) or p.get('type') not in SE_PORT_TYPES or \
                p.get('proto') not in ('tcp', 'udp'):
            raise Refused('a port type otp does not set')
        try:
            n = int(p.get('port'))
        except (TypeError, ValueError):
            raise Refused('a port is a number')
        if not 1 <= n <= 65535:
            raise Refused('a port is 1 to 65535')
        ports.append({'port': n, 'proto': p['proto'], 'type': p['type'],
                      'why': str(p.get('why') or '')[:120]})
    return bools, ports


def se_check(r):
    left = []
    bools, ports = se_want_checked(r, left)
    mode = se_mode()
    conf = se_config()
    out = {'mode': mode, 'config': conf['mode'], 'policy': conf['type'],
           'relabel_pending': os.path.exists(SE_RELABEL), 'cmdline_off': se_cmdline_off(),
           'tools': {'semanage': bool(shutil.which('semanage')),
                     'ausearch': bool(shutil.which('ausearch')),
                     'semodule': bool(shutil.which('semodule'))},
           'module': None, 'labels': [], 'booleans': [], 'ports': [],
           'denials': {'tool': False, 'total': 0, 'groups': []}, 'problems': [],
           'left_out': left}
    if mode == 'absent':
        out['ready'] = False
        return out
    on = mode in ('Enforcing', 'Permissive')
    out['module'] = se_module_in()
    for path, want, why in SE_LABELS:
        if not os.path.exists(path):
            continue
        got = se_label(path) if on else None
        out['labels'].append({'path': path, 'label': got, 'want': want, 'why': why,
                              'ok': (got == want) if on else None})
    for b in bools:
        v = se_bool(b['name']) if on else None
        out['booleans'].append(dict(b, on=v))
    known = se_ports() if on else None
    for p in ports:
        out['ports'].append(dict(p, labelled=(se_port_has(known, p['type'], p['proto'], p['port'])
                                             if known is not None else None)))
    if on:
        out['denials'] = se_denials(se_applied_at())
        # Upgraded from a version before 1.0.248 (1.0.249): when otp's needs were put in was
        # kept in the service's own folder, not read any more (the service could write a time
        # ahead there) - what was refused since the machine started counts again, once.
        out['denials']['since_lost'] = not out['denials'].get('since') and os.path.isfile(
            os.path.join(WEB_DIR, SE_APPLIED)) and se_upgrade_boot_same()
        out['auditd'] = se_auditd()
    probs = out['problems']
    if on:
        if out['module'] is False:
            probs.append('otp\'s module (%s) is not installed' % SE_MODULE)
        probs.extend('%s is labelled %s, not %s (%s)' % (x['path'], x['label'] or '?', x['want'],
                                                         x['why'])
                     for x in out['labels'] if x['ok'] is False)
        probs.extend('the boolean %s is off (%s)' % (x['name'], x['why'])
                     for x in out['booleans'] if x['on'] is False)
        probs.extend('port %d/%s is not labelled %s (%s)' % (x['port'], x['proto'], x['type'],
                                                             x['why'])
                     for x in out['ports'] if x['labelled'] is False)
        if known is None and ports:
            probs.append('semanage is not on this machine - the ports cannot be checked '
                         '(dnf install policycoreutils-python-utils)')
        if out['denials']['total']:
            probs.append(('SELinux refused %d thing(s) since otp\'s needs were put in'
                          if out['denials'].get('since') else
                          'SELinux refused %d thing(s) since the machine started')
                         % out['denials']['total'] + (
                             ' - after the upgrade also what was put right before it (the old note '
                             'of when otp\'s needs were put in is not read any more): they go at '
                             'the next restart of the machine'
                             if out['denials'].get('since_lost') else ''))
        if not out.get('auditd', True):
            # Nothing written down, nothing counted (1.0.234): enforcing let through on no word.
            probs.append('auditd does not run - what SELinux refuses is not written down '
                         '(systemctl enable --now auditd)')
        if not out['denials']['tool']:
            probs.append('ausearch is not on this machine - what SELinux refused cannot be '
                         'read (dnf install audit)')
    out['ready'] = (mode == 'Permissive' and not probs)
    return out


def se_apply(bools, ports, said, mark=True):
    """otp's module, labels, booleans and ports - on a machine where SELinux is on. `mark`:
    when anything was changed, what SELinux refused before no longer counts."""
    changed = False
    # Put in when it is not there, or when it is not the one last put in (1.0.234): a newer
    # module beside the program, which install.sh could not put in, went in here.
    inpol = _read_or(SE_CIL + '.in-policy')
    if os.path.exists(SE_CIL) and shutil.which('semodule') and (
            se_module_in() is not True or inpol != _read_or(SE_CIL)):
        got = _se_run(['semodule', '-i', SE_CIL], 300)
        if got is None or got.returncode != 0:
            raise Refused('semodule -i %s: %s' % (SE_CIL, ((got.stderr or got.stdout)
                                                           if got else '').strip()[-200:]))
        said.append('otp\'s module installed')
        changed = True
        try:
            shutil.copyfile(SE_CIL, SE_CIL + '.in-policy')
        except OSError:
            pass
    for b in bools:
        if se_bool(b['name']) is False:
            got = _se_run(['setsebool', '-P', b['name'], 'on'], 300)
            if got is None or got.returncode != 0:
                raise Refused('setsebool -P %s on: %s' % (b['name'], ((got.stderr or '') if got
                                                                      else '').strip()[-200:]))
            said.append('%s on' % b['name'])
            changed = True
    known = se_ports()
    for p in ports:
        if known is None:
            raise Refused('semanage is not on this machine (dnf install '
                          'policycoreutils-python-utils)')
        if se_port_has(known, p['type'], p['proto'], p['port']):
            continue
        got = _se_run(['semanage', 'port', '-a', '-t', p['type'], '-p', p['proto'],
                       str(p['port'])], 300)
        if got is not None and got.returncode != 0 and 'already defined' in (got.stderr or ''):
            # Never taken from the service it belongs to (1.0.234): -m labelled it for otp's
            # need, and that service could not bind it at its next start.
            raise Refused('port %d/%s is another service\'s in the SELinux policy - choose '
                          'another port for it (%s)' % (p['port'], p['proto'], p['why']))
        if got is None or got.returncode != 0:
            raise Refused('semanage port %d/%s: %s' % (p['port'], p['proto'], ((got.stderr or '')
                                                       if got else '').strip()[-200:]))
        said.append('port %d/%s labelled %s' % (p['port'], p['proto'], p['type']))
        changed = True
    if shutil.which('restorecon'):
        got = _se_run(['restorecon', '-R', '-v'] + [x for x in ('/run/otp', '/var/www/otp',
                                                              '/usr/libexec/keepalived')
                                                  if os.path.exists(x)], 300)
        if got is not None and 'elabel' in (got.stdout or '') + (got.stderr or ''):
            said.append('otp\'s files labelled again')
            changed = True
    # From now on what is refused counts again (1.0.234): what was refused before is what
    # this put right - a second restart was needed before enforcing could be switched on.
    # Only when something was changed, and never on the way to enforcing: what was refused
    # before that still counts there.
    if mark and changed:
        root_state_write(SE_APPLIED, json.dumps({'at': time.time()}))


def se_do(r):
    do = r.get('do')
    left = []
    bools, ports = se_want_checked(r, left)
    said = list(left)
    if do == 'check':
        return se_check(r)
    if do == 'report':
        # Read only (1.0.236): left in the web folder for the daemon, the otp group's to read.
        node = re.sub(r'[^A-Za-z0-9._-]', '', str(r.get('node') or 'node'))[:60] or 'node'
        data = se_report_bytes(r, node)
        write_here_bytes(SE_REPORT_FILE, data)     # by the folder's descriptor, never a link (1.0.248)
        return {'report': SE_REPORT_FILE, 'bytes': len(data), 'at': time.time()}
    mode = se_mode()
    if mode == 'absent':
        raise Refused('there is no SELinux on this machine')
    if do == 'prepare':
        if mode == 'Enforcing':
            raise Refused('SELinux is enforcing already')
        se_config_set('permissive')
        said.append('%s: SELINUX=permissive' % SE_CONFIG)
        if mode == 'Disabled':
            # Every file labelled at the next start, before anything runs (minutes); the
            # booleans and ports are put in by this step again once it is permissive
            # ("Put in what otp needs").
            open(SE_RELABEL, 'a').close()
            said.append('the files are labelled at the next start of the machine')
            if se_cmdline_off() and shutil.which('grubby'):
                got = _se_run(['grubby', '--update-kernel', 'ALL', '--remove-args', 'selinux'],
                              120)
                if got is None or got.returncode != 0:
                    raise Refused('grubby: %s' % ((got.stderr or '') if got else '')[-200:])
                said.append('selinux=0 taken off the kernel\'s command line')
            elif se_cmdline_off():
                said.append('the kernel\'s command line has selinux=0: take it away '
                            '(grubby --update-kernel ALL --remove-args selinux)')
            if os.path.exists(SE_CIL) and shutil.which('semodule'):
                got = _se_run(['semodule', '-i', SE_CIL], 300)    # into the store; may not
                if got is not None and got.returncode == 0:       # work while disabled
                    said.append('otp\'s module installed')
            said.append('restart the machine - it comes up permissive: nothing is refused yet, '
                        'what would be is written down')
        else:
            se_apply(bools, ports, said)
    elif do == 'enforce':
        if mode != 'Permissive':
            raise Refused('SELinux is %s - it goes to enforcing from permissive only'
                          % mode.lower())
        se_apply(bools, ports, said, mark=False)
        c = se_check(r)
        if c['problems']:
            raise Refused('not yet: ' + '; '.join(c['problems'][:4]))
        got = _se_run(['setenforce', '1'], 60)
        if got is None or got.returncode != 0:
            raise Refused('setenforce 1: %s' % ((got.stderr or '') if got else '')[-200:])
        se_config_set('enforcing')
        said.append('SELinux is enforcing, and stays so after a restart')
    elif do == 'permissive':
        if mode == 'Disabled':
            raise Refused('SELinux is disabled - "prepare" makes it permissive')
        if mode == 'Enforcing':
            got = _se_run(['setenforce', '0'], 60)
            if got is None or got.returncode != 0:
                raise Refused('setenforce 0: %s' % ((got.stderr or '') if got else '')[-200:])
        se_config_set('permissive')
        said.append('SELinux is permissive, and stays so after a restart')
    else:
        raise Refused('check, prepare, enforce or permissive')
    out = se_check(r)
    out['said'] = said
    return out


# ---- what SELinux needs, gathered for whoever writes otp's module (1.0.236) -------------------
SE_REPORT_FILE = 'selinux-report.tar.gz'
SE_REPORT_MOST = 2 * 1024 * 1024        # each part at most, before it is packed
SE_REPORT_PATHS = ('/run/otp', '/run/otp/api-token', '/var/lib/otp', '/var/lib/otp/web', '/etc/otp',
                   '/etc/otp/config.json', '/var/www/otp', '/usr/local/lib/otp', '/var/log/otp',
                   '/usr/libexec/keepalived/otp-vip-check', '/etc/nginx/certs', '/etc/nginx/conf.d',
                   '/etc/keepalived/keepalived.conf', '/etc/chrony.conf', '/etc/ssh/sshd_config.d',
                   '/etc/pam.d/sshd', '/run/php-fpm', '/var/lib/pgsql', '/etc/pki/rsyslog')
SE_REPORT_COMMS = ('python', 'otp', 'nginx', 'php-fpm', 'keepalived', 'sshd', 'chronyd', 'postgres',
                   'postmaster', 'mariadbd', 'mysqld', 'rsyslogd', 'auditd', 'otp-vip-check')
SE_REPORT_PORT_TYPES = ('radius_port_t', 'ssh_port_t', 'http_port_t', 'postgresql_port_t',
                        'mysqld_port_t', 'syslogd_port_t', 'snmp_port_t', 'ntp_port_t',
                        'unreserved_port_t', 'vrrp_port_t')


def _se_out(cmd, timeout=120, data=None, light=True):
    """A command's words for the report - what it said, or why it said nothing."""
    if not shutil.which(cmd[0]):
        return '(%s is not on this machine)\n' % cmd[0]
    if light:
        if shutil.which('ionice'):
            cmd = ['ionice', '-c', '3'] + cmd
        if shutil.which('nice'):
            cmd = ['nice', '-n', '19'] + cmd
    try:
        got = subprocess.run(cmd, input=data, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        return '(%s: %s)\n' % (' '.join(cmd), e)
    text = (got.stdout or '') + (('\n--- stderr ---\n' + got.stderr) if got.stderr.strip() else '')
    return _se_cut(text)


def _se_cut(text):
    b = text.encode('utf-8', 'replace')
    if len(b) <= SE_REPORT_MOST:
        return text
    # The newest lines kept: the end of the audit log is what came last.
    return '(the first %d bytes left out - too long)\n' % (len(b) - SE_REPORT_MOST) + \
        b[-SE_REPORT_MOST:].decode('utf-8', 'replace')


def se_report_parts(r):
    """Every part of the report: {name: text}. Read only - nothing is changed."""
    parts = {}
    check = se_check(r)
    parts['check.json'] = json.dumps(check, indent=1, sort_keys=True)
    parts['otp.json'] = json.dumps({'facts': r.get('facts') or {}, 'want': {
        'booleans': r.get('booleans') or [], 'ports': r.get('ports') or []}}, indent=1, sort_keys=True)
    raw = _se_out(['ausearch', '-m', 'AVC,USER_AVC,SELINUX_ERR,USER_SELINUX_ERR', '-ts', 'boot'], 300)
    parts['avc-raw.txt'] = raw
    parts['avc.txt'] = _se_out(['ausearch', '-m', 'AVC,USER_AVC,SELINUX_ERR,USER_SELINUX_ERR',
                                '-ts', 'boot', '-i'], 300)
    if raw.startswith('('):
        parts['audit2why.txt'] = parts['audit2allow.te'] = raw
    else:
        parts['audit2why.txt'] = _se_out(['audit2why'], 300, data=raw)
        parts['audit2allow.te'] = _se_out(['audit2allow', '-m', 'otp_local'], 300, data=raw)
    sysw = []
    for name, cmd in (('os-release', ['cat', '/etc/os-release']), ('kernel', ['uname', '-a']),
                      ('started', ['uptime', '-s']), ('getenforce', ['getenforce']),
                      ('sestatus', ['sestatus', '-v']),
                      ('packages', ['rpm', '-q', 'selinux-policy', 'selinux-policy-targeted',
                                    'policycoreutils', 'policycoreutils-python-utils',
                                    'libselinux-utils', 'audit', 'nginx', 'php-fpm', 'keepalived',
                                    'openssh-server', 'chrony', 'postgresql-server']),
                      ('kernel command line', ['cat', SE_CMDLINE]),
                      ('selinux config', ['cat', SE_CONFIG]),
                      ('auditd', ['systemctl', 'is-active', 'auditd'])):
        sysw.append('==== %s\n%s' % (name, _se_out(cmd, 60, light=False)))
    parts['system.txt'] = '\n'.join(sysw)
    lab = []
    for p in SE_REPORT_PATHS:
        if os.path.lexists(p):
            lab.append(_se_out(['ls', '-Zd', p], 20, light=False).rstrip())
            if os.path.isdir(p):
                lab.append(_se_out(['ls', '-Za', p], 20, light=False).rstrip())
            lab.append('  policy says: ' + _se_out(['matchpathcon', p], 20, light=False).strip())
    parts['labels.txt'] = '\n'.join(lab) + '\n'
    # -o label, not -Z with -o (1.0.266): procps-ng refuses that pair ("can not use output
    # modifiers with user-defined output") on stderr, which the filter below took away whole -
    # processes.txt came out empty on every node.
    ps = _se_out(['ps', '-eo', 'label,user,pid,comm,args'], 60, light=False)
    keep = [x for x in ps.splitlines() if x.startswith('LABEL') or
            any(c in x for c in SE_REPORT_COMMS)]
    if not any(x.startswith('LABEL') for x in keep):
        # ps said something else than its table: kept as it said it, not an empty file.
        keep = ['(ps did not give the table of processes:)'] + ps.splitlines()[:40]
    # Arguments cut to 200: what runs, not every word it was given.
    parts['processes.txt'] = '\n'.join(x[:200] for x in keep) + '\n'
    ports = _se_out(['semanage', 'port', '-l'], 300)
    parts['ports.txt'] = '==== labelled\n' + '\n'.join(
        x for x in ports.splitlines() if x.split()[:1] and x.split()[0] in SE_REPORT_PORT_TYPES) + \
        '\n\n==== listening\n' + _se_out(['ss', '-lntupZ'], 60, light=False)
    bools = _se_out(['getsebool', '-a'], 60, light=False)
    parts['booleans.txt'] = '\n'.join(x for x in bools.splitlines() if re.match(
        r'^(httpd_|authlogin_|nis_enabled|keepalived|daemons_|logging_|ssh|use_nfs|domain_can)',
        x)) + '\n'
    mods = _se_out(['semodule', '-l'], 300)
    parts['modules.txt'] = '==== otp\n' + '\n'.join(
        x for x in mods.splitlines() if 'otp' in x.lower()) + '\n\n==== %s\n%s\n==== in the policy\n%s\n' % (
        SE_CIL, _read_or(SE_CIL) or '(not there)', _read_or(SE_CIL + '.in-policy') or '(none put in yet)')
    parts['README.txt'] = (
        'otp - what SELinux says on this node, for whoever writes otp\'s module (otp_server).\n'
        'Made %s. Nothing was changed to make it.\n\n'
        'check.json      the card: mode, module, labels, booleans, ports, refusals\n'
        'avc*.txt        what SELinux refused since the machine started (raw and readable)\n'
        'audit2why.txt   why; audit2allow.te: what would allow it - a hint, not to be loaded\n'
        'labels.txt      the labels of otp\'s files and what the policy says they should be\n'
        'processes.txt   the domains the programs run in; ports.txt, booleans.txt, modules.txt\n'
        'system.txt      the system, the policy and the packages; otp.json: what otp uses here\n\n'
        'No password, key or token of otp is in it. The audit log holds the command lines of the\n'
        'programs refused something: otp never puts a secret on one - other programs on this\n'
        'machine may. Look through avc*.txt before sending it on.\n' % time.strftime('%Y-%m-%d %H:%M:%S'))
    return parts


def se_report_bytes(r, top):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tf:
        for name, text in se_report_parts(r).items():
            data = text.encode('utf-8', 'replace')
            info = tarfile.TarInfo('%s/%s' % (top, name))
            info.size = len(data)
            info.mtime = int(time.time())
            info.mode = 0o600
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def se_report_write(data, path, uid=0, gid=None):
    """Written whole and put in place, readable by root (and the otp group when asked)."""
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=folder, prefix='.otp-selinux-')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fchmod(f.fileno(), 0o640 if gid is not None else 0o600)
            if gid is not None:
                os.fchown(f.fileno(), uid, gid)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def selinux_part():
    d = web_fd()
    try:
        raw = read_req(SELINUX_ASK, 16384)
    except FileNotFoundError:
        return
    except (Refused, OSError):
        drop_ask(SELINUX_ASK, d)
        return
    drop_ask(SELINUX_ASK, d)
    out = {'at': time.time(), 'ok': False, 'id': ''}
    try:
        r = json.loads(raw.decode('utf-8'))
        if not isinstance(r, dict):
            raise Refused('the request is not an object')
        out['id'] = re.sub(r'[^A-Za-z0-9]', '', str(r.get('id') or ''))[:40]
        out['data'] = se_do(r)
        out['ok'] = True
    except Refused as e:
        out['said'] = str(e)[:400]
    except Exception as e:                              # noqa: BLE001
        out['said'] = 'it went wrong: %s' % str(e)[:300]
    write_here(SELINUX_FILE, json.dumps(out))


def se_report(c):
    """`otp --selinux-check`: what se_check found, for a person."""
    lines = ['SELinux: %s (config: %s%s)' % (c['mode'], c.get('config') or '?',
                                            ', %s' % c['policy'] if c.get('policy') else '')]
    if c['mode'] == 'absent':
        lines.append('  no SELinux on this machine - nothing to do')
        return '\n'.join(lines)
    if c.get('relabel_pending'):
        lines.append('  the files are labelled at the next start of the machine')
    if c.get('cmdline_off'):
        lines.append('  the kernel\'s command line has selinux=0')
    if c['mode'] == 'Disabled':
        lines.append('  disabled - otp runs as always; "Make it ready (permissive)" on the pages '
                     '(Settings - High security) makes it permissive at the next start')
        return '\n'.join(lines)
    lines.append('  module %s: %s' % (SE_MODULE, {True: 'installed', False: 'NOT installed',
                                                  None: '?'}[c['module']]))
    for x in c['labels']:
        lines.append('  %s %s: %s%s' % ('ok  ' if x['ok'] else 'FAIL', x['path'], x['label'] or '?',
                                        '' if x['ok'] else ' (want %s)' % x['want']))
    for x in c['booleans']:
        lines.append('  %s boolean %s: %s - %s' % ('ok  ' if x['on'] else 'FAIL', x['name'],
                                                   'on' if x['on'] else 'off', x['why']))
    for x in c['ports']:
        lines.append('  %s port %d/%s %s - %s' % ('ok  ' if x['labelled'] else 'FAIL', x['port'],
                                                 x['proto'], x['type'], x['why']))
    d = c['denials']
    lines.append('  refused since the start: %s' % (d['total'] if d['tool'] else
                                                    '? (ausearch is not there)'))
    if d.get('settled'):
        lines.append('  refused before, allowed now (not counted): %d' % d['settled'])
    if d.get('since_lost'):
        lines.append('  (after the upgrade counted since the start again - also what was put right before it)')
    for g in d['groups'][:15]:
        lines.append('    %4dx %s -> %s %s { %s } %s' % (g['count'], g['source'], g['target'],
                                                         g['class'], g['perms'], g['what']))
    lines.append('ready for enforcing' if c.get('ready') else
                 ('enforcing' if c['mode'] == 'Enforcing' and not c['problems'] else
                  'not ready: ' + '; '.join(c['problems'][:6]) if c['problems'] else ''))
    return '\n'.join(x for x in lines if x)


# ---- the system's trusted roots (1.0.265) --------------------------------------------
# Certificate authorities of one's own put into the trust of the whole system - curl, dnf,
# LDAPS to a domain controller, SMTP, syslog over TLS, otp's own connections: every program that
# uses the system's trust. Only by the system's own way of adding to it, never by touching the
# distribution's bundle: a file in the folder of local additions, then its own tool -
#   RHEL / AlmaLinux / Rocky: /etc/pki/ca-trust/source/anchors/*.pem, then update-ca-trust extract
#   Debian / Ubuntu:          /usr/local/share/ca-certificates/*.crt, then update-ca-certificates
# Both tools merge that folder with the distribution's list every time they run - also when an
# update of the ca-certificates package runs them - so the distribution's list keeps coming
# with the system's updates and these stay beside it. otp's files are named otp-<sha256 16>.pem
# (.crt): otp lists, writes and removes only those; anything else in the folder was put there by
# somebody else and is only shown. What is asked is always the whole set wanted (`sync`): what
# is missing written, what is otp's and no longer wanted removed, the tool run when anything
# changed. Every certificate is read by openssl here again - nothing of the request is trusted.
OSROOTS_ASK = 'osroots.ask'
OSROOTS_FILE = 'osroots.json'
OSROOTS_MAX = 50                    # otp's certificates at most
OSROOTS_PEM_MAX = 16384             # one certificate, as PEM
OSROOTS_NAME_RE = re.compile(r'^otp-[0-9a-f]{16}\.(pem|crt)\Z')
OSROOTS_BLOCK_RE = re.compile(r'-----BEGIN CERTIFICATE-----([A-Za-z0-9+/=\s]*?)-----END CERTIFICATE-----')
OSROOTS_FLAVOURS = {
    'rhel': {'dir': '/etc/pki/ca-trust/source/anchors', 'ext': '.pem',
             'tool': ['update-ca-trust', 'extract'],
             'bundle': '/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem',
             'pkg': ['rpm', '-q', 'ca-certificates']},
    'debian': {'dir': '/usr/local/share/ca-certificates', 'ext': '.crt',
               'tool': ['update-ca-certificates'],
               'bundle': '/etc/ssl/certs/ca-certificates.crt',
               'pkg': ['dpkg-query', '-W', '-f=ca-certificates-${Version}', 'ca-certificates']}}


def osroots_where():
    """Which way this system adds to its trust - each part overridable for the tests, by the
    environment of the unit (root's alone)."""
    fl = os.environ.get('OTP_OSROOTS_FLAVOUR', '')
    if fl not in OSROOTS_FLAVOURS:
        fl = ''
        if os.path.isdir('/etc/pki/ca-trust/source') or shutil.which('update-ca-trust'):
            fl = 'rhel'
        elif os.path.isdir('/usr/local/share/ca-certificates') or shutil.which('update-ca-certificates'):
            fl = 'debian'
    if not fl:
        return None
    w = dict(OSROOTS_FLAVOURS[fl], flavour=fl)
    w['dir'] = os.environ.get('OTP_OSROOTS_DIR') or w['dir']
    w['bundle'] = os.environ.get('OTP_OSROOTS_BUNDLE') or w['bundle']
    if os.environ.get('OTP_OSROOTS_EXTRACT'):
        w['tool'] = os.environ['OTP_OSROOTS_EXTRACT'].split()
    if 'OTP_OSROOTS_PKG' in os.environ:
        w['pkg'] = os.environ['OTP_OSROOTS_PKG'].split()
    return w


def osroots_blocks(text):
    """Each certificate of a text as (pem, der) - nothing but certificates: a private key, or a
    text with no certificate in it, refused whole."""
    text = str(text or '')
    if re.search(r'PRIVATE KEY|BEGIN ENCRYPTED|BEGIN PKCS7|BEGIN TRUSTED CERTIFICATE', text):
        raise Refused('no private key and nothing but certificates (-----BEGIN CERTIFICATE-----)')
    out = []
    for body in OSROOTS_BLOCK_RE.findall(text):
        b64 = re.sub(r'\s+', '', body)
        try:
            der = base64.b64decode(b64, validate=True)
        except ValueError:
            raise Refused('a certificate that is not base64')
        if not der or len(der) > OSROOTS_PEM_MAX * 3 // 4:
            raise Refused('a certificate of %d bytes - one is a few kB at most' % len(der))
        enc = base64.b64encode(der).decode('ascii')
        pem = '-----BEGIN CERTIFICATE-----\n%s\n-----END CERTIFICATE-----\n' % '\n'.join(
            enc[i:i + 64] for i in range(0, len(enc), 64))
        out.append((pem, der))
    if not out:
        raise Refused('no certificate in it (-----BEGIN CERTIFICATE-----)')
    return out


def _osroots_time(s):
    import calendar
    try:
        return calendar.timegm(time.strptime(re.sub(r'\s+', ' ', s.strip()), '%b %d %H:%M:%S %Y %Z'))
    except ValueError:
        return 0


def osroots_facts(pem, der=None):
    """What one certificate is, as openssl reads it: its names, its time, its key, whether it is
    an authority - and what stands against it (`refused`) or is to be known (`warn`)."""
    if der is None:
        der = osroots_blocks(pem)[0][1]
    txt = openssl(['x509', '-noout', '-text', '-nameopt', 'RFC2253'], 'not a certificate openssl reads',
                  data=pem)

    def one(rx):
        m = re.search(rx, txt, re.M)
        return m.group(1).strip() if m else ''
    f = {'fp': hashlib.sha256(der).hexdigest(), 'subject': one(r'^\s*Subject: ?(.*)$')[:400],
         'issuer': one(r'^\s*Issuer: ?(.*)$')[:400],
         'not_before': _osroots_time(one(r'Not Before\s*: (.*)$')),
         'not_after': _osroots_time(one(r'Not After\s*: (.*)$')),
         'sig': one(r'Signature Algorithm: (\S+)')[:60]}
    cn = re.search(r'(?:^|,)CN=((?:\\.|[^,])*)', f['subject'])
    f['cn'] = (cn.group(1) if cn else f['subject'])[:200]
    alg = one(r'Public Key Algorithm: (\S+)')
    bits = one(r'Public-Key: \((\d+) bit\)')
    curve = one(r'NIST CURVE: (\S+)') or one(r'ASN1 OID: (\S+)')
    if alg == 'rsaEncryption':
        f['key'] = 'RSA %s' % bits
    elif alg == 'id-ecPublicKey':
        f['key'] = 'EC %s' % (curve or bits)
    elif alg:
        f['key'] = alg.replace('ED25519', 'Ed25519').replace('ED448', 'Ed448')[:40]
    else:
        f['key'] = '?'
    f['bits'] = int(bits) if bits.isdigit() else 0
    bc = re.search(r'X509v3 Basic Constraints:.*\n\s*(CA:(TRUE|FALSE))', txt)
    f['ca'] = bool(bc and bc.group(2) == 'TRUE')
    ku = re.search(r'X509v3 Key Usage:.*\n\s*(.*)', txt)
    f['ku_sign'] = None if not ku else ('Certificate Sign' in ku.group(1))
    f['root'] = f['subject'] == f['issuer']
    f['kind'] = 'root' if f['root'] else 'intermediate'
    refused, warn = [], []
    now = time.time()
    if not bc:
        refused.append('it says nothing of being an authority (no basicConstraints CA:TRUE) - '
                       'only a certificate authority goes here')
    elif not f['ca']:
        refused.append('it is not a certificate authority (CA:FALSE) - a server\'s own certificate '
                       'does not go here')
    if f['ku_sign'] is False:
        refused.append('its key usage does not let it sign certificates (no keyCertSign)')
    if f['not_after'] and f['not_after'] < now:
        warn.append('it ran out on %s - nothing it signed is trusted' % time.strftime(
            '%Y-%m-%d', time.gmtime(f['not_after'])))
    if f['not_before'] and f['not_before'] > now + 300:
        warn.append('it is valid only from %s' % time.strftime('%Y-%m-%d', time.gmtime(f['not_before'])))
    if not f['root'] and re.match(r'(?i)(sha1|md5|md2)', f['sig']):
        warn.append('it is signed with %s - the system\'s crypto policy (DEFAULT) refuses it, and '
                    'every chain through it' % f['sig'])
    if f['key'].startswith('RSA') and 0 < f['bits'] < 2048:
        warn.append('its key has %d bits - the system\'s crypto policy (DEFAULT) refuses fewer '
                    'than 2048' % f['bits'])
    f['refused'], f['warn'] = refused, warn
    return f


def osroots_dir_ok(d, make=False):
    """The folder of local additions: a folder of root's, never a link."""
    try:
        st = os.lstat(d)
    except FileNotFoundError:
        if not make:
            return False
        os.makedirs(d, 0o755, exist_ok=True)
        st = os.lstat(d)
    if not stat.S_ISDIR(st.st_mode):
        raise Refused('%s is not a folder (a link?) - nothing is written there' % d)
    if st.st_uid != 0 or st.st_mode & 0o022:
        raise Refused('%s is not root\'s alone (owner %d, mode %o) - nothing is written there'
                      % (d, st.st_uid, stat.S_IMODE(st.st_mode)))
    return True


def _osroots_read(path, most=1048576):
    """A plain file's bytes - None for a link (never followed), a folder, a pipe."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as e:
        if e.errno in (errno.ELOOP, errno.EISDIR, errno.ENXIO):
            return None
        raise
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        data = os.read(fd, most + 1)
    finally:
        os.close(fd)
    return data[:most]


def osroots_files(d):
    """[(relative name, path)] of the folder - one level of subfolders too (Debian reads them)."""
    out = []
    try:
        top = sorted(os.listdir(d))
    except OSError:
        return out
    for n in top[:500]:
        p = os.path.join(d, n)
        if os.path.isdir(p) and not os.path.islink(p):
            try:
                out += [(n + '/' + m, os.path.join(p, m)) for m in sorted(os.listdir(p))[:200]]
            except OSError:
                pass
        else:
            out.append((n, p))
    return out


def osroots_cert_of_file(path):
    """The certificates of a file somebody else put there - PEM or DER - with their facts."""
    raw = _osroots_read(path)
    if raw is None:
        return None
    text = raw.decode('ascii', 'replace')
    if '-----BEGIN CERTIFICATE-----' not in text:
        try:
            got = subprocess.run(['openssl', 'x509', '-inform', 'DER'], input=raw, capture_output=True,
                                 timeout=30)
            if got.returncode != 0:
                return []
            text = got.stdout.decode('ascii', 'replace')
        except (OSError, subprocess.SubprocessError):
            return []
    out = []
    try:
        blocks = OSROOTS_BLOCK_RE.findall(text) and osroots_blocks(
            '\n'.join(m.group(0) for m in OSROOTS_BLOCK_RE.finditer(text)))
    except Refused:
        return []
    for pem, der in (blocks or [])[:20]:
        try:
            f = osroots_facts(pem, der)
            out.append({k: f[k] for k in ('fp', 'cn', 'subject', 'issuer', 'not_before', 'not_after',
                                          'key', 'kind', 'ca')})
        except Refused:
            continue
    return out


def osroots_bundle(w):
    """The system's own list as its tool made it last: how many, how large, when - and the
    package that brings it, so it is seen that the system's updates keep it coming."""
    out = {'path': w['bundle'], 'count': 0, 'bytes': 0, 'at': 0}
    try:
        st = os.stat(w['bundle'])
        out.update(bytes=st.st_size, at=st.st_mtime)
        with open(w['bundle'], 'rb') as f:
            out['count'] = f.read(64 * 1048576).count(b'-----BEGIN CERTIFICATE-----')
    except OSError:
        out['missing'] = True
    pkg = ''
    if w.get('pkg'):
        try:
            got = subprocess.run(w['pkg'], capture_output=True, text=True, timeout=30)
            if got.returncode == 0:
                pkg = got.stdout.strip().splitlines()[0][:120] if got.stdout.strip() else ''
        except (OSError, subprocess.SubprocessError, IndexError):
            pkg = ''
    out['package'] = pkg
    return out


def _osroots_in_bundle(w, ders):
    """Which of these the tool put into the system's list: their base64 found in it."""
    try:
        with open(w['bundle'], 'rb') as f:
            flat = re.sub(rb'\s+', b'', f.read(64 * 1048576))
    except OSError:
        return {}
    return {hashlib.sha256(d).hexdigest(): base64.b64encode(d) in flat for d in ders}


def osroots_read(w):
    """otp's own, the others', the system's list."""
    ours, others = [], []
    if w and os.path.isdir(w['dir']):
        for rel, p in osroots_files(w['dir']):
            if OSROOTS_NAME_RE.match(rel):
                raw = _osroots_read(p, 65536)
                if raw is None:
                    others.append({'file': rel, 'certs': [], 'link': os.path.islink(p)})
                    continue
                try:
                    (pem, der), = osroots_blocks(raw.decode('ascii', 'replace'))
                    f = osroots_facts(pem, der)
                    f.pop('refused', None)
                    f.update(file=rel, der=der)
                    ours.append(f)
                except (Refused, ValueError):
                    ours.append({'file': rel, 'broken': True})
            else:
                if os.path.islink(p):
                    try:
                        to = os.readlink(p)[:300]
                    except OSError:
                        to = '?'
                    others.append({'file': rel, 'link': to, 'certs': []})
                    continue
                # Read up to 60 files of others' (each openssl run takes its time); the rest named.
                read_others = sum(1 for o in others if o.get('certs'))
                others.append({'file': rel, 'certs': (osroots_cert_of_file(p) or []) if read_others < 60 else []})
    inb = _osroots_in_bundle(w, [f['der'] for f in ours if f.get('der')]) if w else {}
    for f in ours:
        f.pop('der', None)
        if f.get('fp'):
            f['in_bundle'] = inb.get(f['fp'])
    return {'ours': ours, 'others': others[:200], 'system': osroots_bundle(w) if w else {},
            'flavour': (w or {}).get('flavour', ''), 'dir': (w or {}).get('dir', ''),
            'tool': ' '.join((w or {}).get('tool') or []),
            'tool_there': bool(w and shutil.which(w['tool'][0]))}


def _osroots_put(d, name, pem):
    """Written beside it under a name of its own and renamed into place: root's, 0644."""
    fd, tmp = tempfile.mkstemp(prefix='.otp-', dir=d)
    try:
        os.fchmod(fd, 0o644)
        try:
            os.fchown(fd, 0, 0)
        except OSError:
            pass
        with os.fdopen(fd, 'w') as f:
            fd = None
            f.write(pem)
        os.replace(tmp, os.path.join(d, name))
    except BaseException:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def osroots_sync(w, certs, force=False):
    """The folder made to hold exactly the certificates wanted of otp's - the others' left as they
    are - and the system's tool run when anything changed. (said, refused [(fp, why)])."""
    if not w:
        raise Refused('this system has neither update-ca-trust (RHEL, AlmaLinux, Rocky) nor '
                      'update-ca-certificates (Debian, Ubuntu)')
    if not isinstance(certs, list) or len(certs) > OSROOTS_MAX:
        raise Refused('the certificates wanted: a list of %d at most' % OSROOTS_MAX)
    want, refused = {}, []
    for c in certs:
        if not isinstance(c, str) or len(c) > OSROOTS_PEM_MAX:
            raise Refused('each certificate as PEM text of %d bytes at most' % OSROOTS_PEM_MAX)
        blocks = osroots_blocks(c)
        if len(blocks) != 1:
            raise Refused('one certificate in each')
        pem, der = blocks[0]
        f = osroots_facts(pem, der)
        if f['refused']:
            refused.append({'fp': f['fp'], 'cn': f['cn'], 'why': '; '.join(f['refused'])})
            continue
        want['otp-%s%s' % (f['fp'][:16], w['ext'])] = pem
    osroots_dir_ok(w['dir'], make=bool(want))
    said, changed = [], False
    have = {rel: p for rel, p in osroots_files(w['dir']) if OSROOTS_NAME_RE.match(rel)} \
        if os.path.isdir(w['dir']) else {}
    for name, pem in sorted(want.items()):
        p = have.get(name)
        if p is not None:
            raw = _osroots_read(p, 65536)
            if raw is not None and raw.decode('ascii', 'replace') == pem and not os.path.islink(p):
                continue
            os.unlink(p)            # changed by somebody, or a link: put back as it is wanted
        _osroots_put(w['dir'], name, pem)
        said.append('added %s' % name)
        changed = True
        if shutil.which('restorecon') and os.path.isdir('/sys/fs/selinux') and \
                not os.environ.get('OTP_OSROOTS_DIR'):
            subprocess.run(['restorecon', '-F', os.path.join(w['dir'], name)], capture_output=True)
    for name, p in sorted(have.items()):
        if name not in want:
            os.unlink(p)
            said.append('removed %s' % name)
            changed = True
    tool_said = ''
    if changed or force:
        if not shutil.which(w['tool'][0]):
            raise Refused('%s is not on this machine - the files are in %s, the system\'s list is '
                          'not made again until it runs' % (w['tool'][0], w['dir']))
        got = subprocess.run(w['tool'], capture_output=True, text=True, timeout=300)
        if got.returncode != 0:
            raise Refused('%s ended with %d: %s' % (' '.join(w['tool']), got.returncode,
                                                    ((got.stderr or got.stdout).strip() or '-')[-300:]))
        tool_said = ' '.join(w['tool'])
        said.append('%s run' % tool_said)
    return said, refused


def osroots_do(r):
    w = osroots_where()
    do = r.get('do')
    if do == 'list':
        return dict(osroots_read(w), said=[], refused=[])
    if do == 'check':
        # A text read for the pages: what each certificate in it is - nothing written.
        text = r.get('text')
        if not isinstance(text, str) or len(text) > OSROOTS_MAX * OSROOTS_PEM_MAX:
            raise Refused('the certificates as PEM text')
        out = []
        for pem, der in osroots_blocks(text)[:OSROOTS_MAX + 1]:
            out.append(dict(osroots_facts(pem, der), pem=pem))
        return {'certs': out}
    if do == 'sync':
        said, refused = osroots_sync(w, r.get('certs'), bool(r.get('force')))
        return dict(osroots_read(w), said=said, refused=refused)
    raise Refused('list, check or sync')


def osroots_part():
    d = web_fd()
    try:
        raw = read_req(OSROOTS_ASK, OSROOTS_MAX * OSROOTS_PEM_MAX * 2 + 65536)
    except FileNotFoundError:
        return
    except (Refused, OSError):
        drop_ask(OSROOTS_ASK, d)
        return
    drop_ask(OSROOTS_ASK, d)
    out = {'at': time.time(), 'ok': False, 'id': ''}
    try:
        r = json.loads(raw.decode('utf-8'))
        if not isinstance(r, dict):
            raise Refused('the request is not an object')
        out['id'] = re.sub(r'[^A-Za-z0-9]', '', str(r.get('id') or ''))[:40]
        out['data'] = osroots_do(r)
        out['ok'] = True
    except Refused as e:
        out['said'] = str(e)[:400]
    except Exception as e:                              # noqa: BLE001
        out['said'] = 'it went wrong: %s' % str(e)[:300]
    write_here(OSROOTS_FILE, json.dumps(out))


def sshd_overdue():
    """A change of sshd on trial whose time is up and that nobody kept, put back (1.0.234):
    its timer, systemd's own, does not outlive a restart of the machine - and an admin locked
    out by the change restarts it. The trial was kept for good."""
    t = sshd_trial_read()
    try:
        until = float((t or {}).get('until') or 0)
    except (TypeError, ValueError):
        until = 0
    if until and time.time() > until + 30:
        sshd_put_back('not kept in time (its timer did not outlive a restart)')


def serve():
    d = web_fd()
    try:
        sshd_overdue()
    except Exception as e:                              # noqa: BLE001
        print('otp_web.py: a change of sshd on trial: %s' % e, file=sys.stderr)
    try:
        pglog_part()
    except Exception as e:                              # noqa: BLE001
        print('otp_web.py: the PostgreSQL log: %s' % e, file=sys.stderr)
    try:
        pgtls_part()
    except Exception as e:                              # noqa: BLE001
        print('otp_web.py: the database link: %s' % e, file=sys.stderr)
    try:
        fw_read_part()
    except Exception as e:                              # noqa: BLE001
        print('otp_web.py: the firewall as it is: %s' % e, file=sys.stderr)
    try:
        net_part()
    except Exception as e:                              # noqa: BLE001
        print('otp_web.py: the network: %s' % e, file=sys.stderr)
    try:
        ntp_part()
    except Exception as e:                              # noqa: BLE001
        print('otp_web.py: the time: %s' % e, file=sys.stderr)
    try:
        console_part()
    except Exception as e:                              # noqa: BLE001
        print('otp_web.py: the console at login: %s' % e, file=sys.stderr)
    try:
        sshkeys_part()
    except Exception as e:                              # noqa: BLE001
        print('otp_web.py: root\'s SSH keys: %s' % e, file=sys.stderr)
    try:
        users_part()
    except Exception as e:                              # noqa: BLE001
        print('otp_web.py: the local users: %s' % e, file=sys.stderr)
    try:
        osup_part()
    except Exception as e:                              # noqa: BLE001
        print('otp_web.py: the updates of the system: %s' % e, file=sys.stderr)
    try:
        sshd_part()
    except Exception as e:                              # noqa: BLE001
        print('otp_web.py: the SSH server: %s' % e, file=sys.stderr)
    try:
        logs_part()
    except Exception as e:                              # noqa: BLE001
        print('otp_web.py: the journal and the logs: %s' % e, file=sys.stderr)
    try:
        selinux_part()
    except Exception as e:                              # noqa: BLE001
        print('otp_web.py: SELinux: %s' % e, file=sys.stderr)
    try:
        osroots_part()
    except Exception as e:                              # noqa: BLE001
        print('otp_web.py: the system\'s trusted roots: %s' % e, file=sys.stderr)
    try:
        os.replace('request.json', 'request.taken', src_dir_fd=d, dst_dir_fd=d)
    except FileNotFoundError:
        return 0
    except OSError:
        # request.taken a folder, or request.json one (1.0.94): both taken
        # away, not left to start this service over and over.
        drop_ask('request.taken', d)
        drop_ask('request.json', d)
        return 1
    last = status_read()
    out = {'at': time.time(), 'applied': last.get('applied') or {}, 'dh': last.get('dh') or {}}
    try:
        try:
            raw = json.loads(read_req('request.taken').decode('utf-8'))
        except ValueError as e:
            raise Refused('the request does not read: %s' % e)
        if isinstance(raw, dict):
            out.update(id=re.sub(r'[^A-Za-z0-9]', '', str(raw.get('id') or ''))[:32],
                       hash=re.sub(r'[^0-9a-f]', '', str(raw.get('hash') or ''))[:64])
        PROGRESS['id'] = str(out.get('id') or '')
        progress('checking what was asked', 1)
        r = checked(raw)
        out.update(id=r['id'], hash=r['hash'], vip_on=r['vip']['on'])
        # The firewall on its own (1.0.248): nginx or keepalived refusing a step stopped the
        # firewall's too - a trial's rules put back never reached iptables.
        errs, said = [], []
        try:
            said_n, dh = nginx_part(r, last)
            out['dh'] = dict(out['dh'], **dh)
            said += said_n
            said_v, keep = vip_part(r, last.get('applied') or {})
            said += said_v
            out['applied'] = keep
        except Refused as e:
            errs.append(str(e))
        except Exception as e:                          # noqa: BLE001
            errs.append('it broke: %s' % e)
        try:
            said_f, fw = fw_part(r['fw'])
            said += said_f
            out['fw'] = fw
        except Refused as e:
            errs.append(str(e))
        except Exception as e:                          # noqa: BLE001
            errs.append('it broke: %s' % e)
        if errs:
            out.update(state='failed', said=errs + [s for s in said if s])
        else:
            out.update(state='done', said=[s for s in said if s], access=access_now())
    except Refused as e:
        out.update(state='failed', said=[str(e)])
    except Exception as e:                              # noqa: BLE001 - said, never lost
        out.update(state='failed', said=['it broke: %s' % e])
    finally:
        for name in ('request.taken', 'progress.json'):
            try:
                os.unlink(name, dir_fd=d)
            except OSError:
                pass
    write_here('status.json', json.dumps(out))
    return 0


def main(argv):
    if argv[:1] == ['--status']:
        print(json.dumps({'keepalived': ka_ours(), 'nginx_vip': os.path.exists(NGINX_VIP),
                          'status': status_read()}))
        return 0
    if os.geteuid() != 0:
        print('otp_web.py: root only', file=sys.stderr)
        return 2
    if argv[:1] == ['--selinux-report'] and len(argv) >= 2:
        # `otp --selinux-report` (1.0.236): what otp needs and what came on stdin, into a file.
        want = {}
        try:
            want = json.loads(sys.stdin.read(65536) or '{}')
        except ValueError:
            want = {}
        want = want if isinstance(want, dict) else {}
        out = argv[1]
        node = re.sub(r'[^A-Za-z0-9._-]', '', str(want.get('node') or 'node'))[:60] or 'node'
        try:
            data = se_report_bytes(want, node)
            se_report_write(data, out)
        except (Refused, OSError) as e:
            print('otp_web.py: %s' % e, file=sys.stderr)
            return 2
        print(out)
        return 0
    if argv[:1] == ['--selinux-do'] and len(argv) >= 2:
        # `otp --selinux prepare|apply|enforce|permissive` (1.0.236): one step on this machine.
        want = {}
        try:
            want = json.loads(sys.stdin.read(65536) or '{}')
        except ValueError:
            want = {}
        do = {'apply': 'prepare'}.get(argv[1], argv[1])
        try:
            c = se_do(dict(want if isinstance(want, dict) else {}, do=do))
        except Refused as e:
            print('otp_web.py: %s' % e, file=sys.stderr)
            return 2
        said = c.pop('said', []) if isinstance(c, dict) else []
        print(json.dumps(c) if '--json' in argv else
              '\n'.join(['done: ' + x for x in said] + [se_report(c)]))
        return 0
    if argv[:1] == ['--selinux-check']:
        # `otp --selinux-check` (1.0.233): what otp needs here comes on stdin from the otp
        # command, as JSON; nothing is changed.
        want = {}
        if '--want-stdin' in argv:
            try:
                want = json.loads(sys.stdin.read(65536) or '{}')
            except ValueError:
                want = {}
        try:
            c = se_check(want if isinstance(want, dict) else {})
        except Refused as e:
            print('otp_web.py: %s' % e, file=sys.stderr)
            return 2
        print(json.dumps(c) if '--json' in argv else se_report(c))
        return 0 if (c['mode'] in ('absent', 'Disabled') or not c['problems']) else 1
    if argv[:1] == ['--sshd-back']:
        # The timer of a change of sshd on trial (1.0.163): not kept in time.
        sshd_put_back()
        return 0
    if argv[:1] == ['--pam-off']:
        # otp taken away (1.0.206): sshd's PAM no longer asks an otp that is not
        # there - every password and code over SSH was refused after an
        # uninstall - and no change on trial is left with a timer that runs
        # what is gone.
        said = pam_set({'radius': False}, '', 0)
        t = sshd_trial_read()
        if t:
            sshd_disarm(t)
            _drop(SSHD_STATE)
        # Passwords kept off (1.0.252): with otp's code they came through keyboard-interactive,
        # which otp's PAM block ended in pam_deny - the block gone, the system's PAM let the Unix
        # password alone in over it.
        drop = os.path.join(SSH_DIR, SSHD_DROPIN)
        text = _read_or(drop)
        # Not where a key and then the code is asked (AuthenticationMethods ...keyboard-interactive):
        # switched off, those users - root too - could no longer sign in at all, and with the line
        # for everybody sshd did not start again. There it stays as before: a key, then the system's
        # PAM.
        if text and re.search(r'(?mi)^\s*PasswordAuthentication\s+no\b', text) and \
                re.search(r'(?mi)^\s*KbdInteractiveAuthentication\s+yes\b', text) and \
                not re.search(r'(?mi)^\s*AuthenticationMethods\b.*keyboard-interactive', text):
            new = re.sub(r'(?mi)^(\s*)KbdInteractiveAuthentication\s+yes\b',
                         r'\1KbdInteractiveAuthentication no', text)
            _put_file(drop, new, 0o600)
            try:
                sshd_reload()
                said = (said + '; ' if said else '') + 'keyboard-interactive off again, as passwords are'
            except Refused as e:
                said = (said + '; ' if said else '') + str(e)
        print(said or 'sshd\'s PAM had nothing of otp in it')
        return 0
    if argv[:1] == ['--os-job'] and len(argv) >= 3 and argv[2] in ('check', 'upgrade'):
        return osup_job(re.sub(r'[^A-Za-z0-9]', '', argv[1])[:40], argv[2],
                        argv[3:4] == ['security'])
    return serve()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
