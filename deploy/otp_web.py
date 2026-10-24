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
"""
import ipaddress
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

STATE_DIR = os.environ.get('OTP_STATE', '/var/lib/otp')
WEB_DIR = os.path.join(STATE_DIR, 'web')
KA_CONF = os.environ.get('OTP_VIP_KA_CONF', '/etc/keepalived/keepalived.conf')
NGINX_DIR = os.environ.get('OTP_VIP_NGINX_DIR', '/etc/nginx/conf.d')
NGINX_MAIN = os.path.join(NGINX_DIR, 'otp.conf')
NGINX_VIP = os.path.join(NGINX_DIR, 'otp_vip.conf')   # read after otp.conf: never the default server
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
PGLOG_FILE = 'pglog.json'
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


def write_root(path, text, mode):
    """A file of root's, replaced whole."""
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.otp-', dir=folder)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---- what a request may hold ---------------------------------------------------------
NAME_RE = re.compile(r'^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)'
                     r'(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$')
IFACE_RE = re.compile(r'^[A-Za-z0-9_.:-]{1,15}\Z')
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


def iface_of(address):
    """The interface that holds `address` here."""
    out = run(['ip', '-o', 'addr', 'show'], 'ip addr')
    for line in out.splitlines():
        f = line.split()
        if len(f) >= 4 and f[3].split('/')[0] == address:
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
    text = '    %-25s %s;' % (name, value)
    if at:
        lines[at[0]] = text
        for n in reversed(at[1:]):
            del lines[n]
    else:
        lines.insert(insert_at if insert_at is not None else 1, text)
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


def tls_into(block, t, files, had_dh):
    """A server { } with the TLS of `t`: its files written, its lines set.
    Returns (block, words, dh made)."""
    said = []
    progress('writing the certificate and the TLS settings', 3)
    if t['pem']:
        full = t['pem']['cert'] + t['pem']['chain']
        write_root(files['cert'], full, 0o644)
        write_root(files['key'], t['pem']['key'], 0o600)
        block = set_directive(block, 'ssl_certificate', files['cert'])
        block = set_directive(block, 'ssl_certificate_key', files['key'])
        if t['pem']['root']:
            write_root(files['root'], t['pem']['root'] + t['pem']['chain'], 0o644)
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
              'root': os.path.join(CERT_DIR, 'otp-ca.pem'),
              'dh': os.path.join(CERT_DIR, 'otp-dh.pem')}
VIP_FILES = {'cert': os.path.join(CERT_DIR, 'otp-vip.pem'),
             'key': os.path.join(CERT_DIR, 'otp-vip.key'),
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
            os.chmod(tmp, was[1])
            os.replace(tmp, p)
            # Its SELinux label too, not the folder's (1.0.57).
            if shutil.which('restorecon'):
                subprocess.run(['restorecon', p], capture_output=True)


SYSCTL_FILE = '/etc/sysctl.d/90-otp-vip.conf'


def nonlocal_bind(family):
    """nginx may listen on the web address on the node that does not hold
    it - so it answers at once when the address comes over."""
    key = 'net.ipv6.ip_nonlocal_bind' if family == 6 else 'net.ipv4.ip_nonlocal_bind'
    want = '%s\n%s = 1\n' % (MARK, key)
    try:
        with open(SYSCTL_FILE) as f:
            if f.read() == want:
                return ''
    except OSError:
        pass
    if NO_SERVICES:
        return ''
    write_root(SYSCTL_FILE, want, 0o644)
    subprocess.run(['sysctl', '-w', '%s=1' % key], capture_output=True)
    return 'sysctl: %s = 1 (nginx listens on the web address on both nodes)' % key


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
    paths = [NGINX_MAIN, NGINX_VIP] + list(NODE_FILES.values()) + list(VIP_FILES.values())
    snap = snapshot(paths)
    changed = False
    try:
        try:
            with open(NGINX_MAIN) as f:
                main = f.read()
        except OSError as e:
            raise Refused('otp\'s nginx file cannot be read (%s): %s' % (NGINX_MAIN, e))
        if r.get('access'):
            new_main = access_into(main, r['access'])
            if new_main != main:
                write_root(NGINX_MAIN, new_main, 0o644)
                main, changed = new_main, True
                said.append('nginx: who may reach the enrolment, administration and health '
                            'pages set')
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
            said.append(nonlocal_bind(vip['family']))
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
        if changed and not NO_SERVICES:
            progress('asking nginx, and reloading it', 4)
            t = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
            if t.returncode != 0:
                raise Refused('nginx does not take it, so it is as it was: %s'
                              % ((t.stderr or '').strip().splitlines() or ['?'])[-1][:300])
            subprocess.run(['systemctl', 'reload', 'nginx'], capture_output=True)
            said.append('nginx reloaded')
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
        v['iface'] = iface_of(v['own'])
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
    if out['do'] not in ('server', 'hba', 'peer', 'hba_off', 'server_off'):
        raise Refused('server, hba, peer, hba_off or server_off')
    try:
        out['port'] = int(r.get('port') or 5432)
    except (TypeError, ValueError):
        raise Refused('the port is a number')
    if not 1 <= out['port'] <= 65535:
        raise Refused('the port is 1 to 65535')
    for k in ('db', 'user'):
        if not PG_NAME_RE.match(str(r.get(k) or '')):
            raise Refused('the database and its account are plain names')
        out[k] = str(r[k])
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
    for name, text, mode in (('otp-ha.key', r['key'], 0o600), ('otp-ha.crt', r['cert'], 0o644)):
        path = os.path.join(data, name)
        fd, tmp = tempfile.mkstemp(prefix='.otp-', dir=data)
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(text)
            os.chmod(tmp, mode)
            if uid is not None:
                os.chown(tmp, uid, gid if gid is not None else -1)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
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
        raise Refused('PostgreSQL did not take the certificate on reload - its log says why '
                      '(Settings → High availability → The errors)')
    end = openssl(['x509', '-noout', '-enddate'], 'the certificate', r['cert'])
    import ssl as _ssl
    return {'said': 'PostgreSQL answers over TLS with its certificate from the cluster\'s '
                    'authority', 'data_dir': data,
            'cert_end': float(_ssl.cert_time_to_seconds(end.strip().split('=', 1)[-1]))}


def pgtls_hba(r):
    if not r['peer']:
        raise Refused('the other node\'s address is not known here')
    net = pg_peer_net(r['peer'])
    if net.startswith('127.') or net == '::1/128':
        return {'said': 'the other node is on this machine (%s): its line in pg_hba.conf is '
                        'this node\'s own, left as it is' % r['peer']}
    hba = pg_sql(r['port'], 'SHOW hba_file')
    if not hba.startswith('/') or not os.path.isfile(hba):
        raise Refused('pg_hba.conf was not found (%s)' % hba[:100])
    with open(hba) as f:
        text = f.read()
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
    st = os.stat(hba)
    shutil.copy2(hba, hba + '.otp-before-tls')
    write_root(hba, '\n'.join(lines), stat.S_IMODE(st.st_mode))
    os.chown(hba, st.st_uid, st.st_gid)
    try:
        pg_sql(r['port'], 'SELECT pg_reload_conf()')
        bad = pg_sql(r['port'], 'SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL')
        if bad not in ('', '0'):
            raise Refused('PostgreSQL does not read pg_hba.conf as written')
    except Refused:
        shutil.copy2(hba + '.otp-before-tls', hba)
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
    hba = pg_sql(r['port'], 'SHOW hba_file')
    if not hba.startswith('/') or not os.path.isfile(hba):
        raise Refused('pg_hba.conf was not found (%s)' % hba[:100])
    with open(hba) as f:
        text = f.read()
    lines, moved, there = text.split('\n'), 0, False
    for i, line in enumerate(lines):
        f = line.split()
        if len(f) >= 5 and f[0] in ('host', 'hostssl') and f[1] == r['db'] and f[2] == r['user']:
            if f[3] == net:
                there = True
            elif old and f[3] == old and not old.startswith('127.') and old != '::1/128':
                lines[i] = line.replace(old, net, 1)
                moved += 1
                there = True
    if not there:
        lines.insert(0, 'host    %s    %s    %s    scram-sha-256' % (r['db'], r['user'], net))
        lines.insert(0, '# otp high availability: the other node (%s)' % time.strftime('%Y-%m-%d'))
    new_text = '\n'.join(lines)
    if new_text == text:
        return {'said': 'pg_hba.conf already lets %s in' % r['peer']}
    st = os.stat(hba)
    shutil.copy2(hba, hba + '.otp-before-readdress')
    write_root(hba, new_text, stat.S_IMODE(st.st_mode))
    os.chown(hba, st.st_uid, st.st_gid)
    try:
        pg_sql(r['port'], 'SELECT pg_reload_conf()')
        bad = pg_sql(r['port'], 'SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL')
        if bad not in ('', '0'):
            raise Refused('PostgreSQL does not read pg_hba.conf as written')
    except Refused:
        shutil.copy2(hba + '.otp-before-readdress', hba)
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
    hba = pg_sql(r['port'], 'SHOW hba_file')
    if not hba.startswith('/') or not os.path.isfile(hba):
        raise Refused('pg_hba.conf was not found (%s)' % hba[:100])
    with open(hba) as f:
        text = f.read()
    lines, changed = text.split('\n'), 0
    for i, line in enumerate(lines):
        f = line.split()
        if len(f) >= 5 and f[0] == 'hostssl' and f[1] == r['db'] and f[2] == r['user'] and \
                f[3] == net:
            lines[i] = re.sub(r'^hostssl(\s)', r'host\1', line, count=1)
            changed += 1
    if not changed:
        return {'said': 'pg_hba.conf already lets the other node in without TLS'}
    st = os.stat(hba)
    shutil.copy2(hba, hba + '.otp-before-tls-off')
    write_root(hba, '\n'.join(lines), stat.S_IMODE(st.st_mode))
    os.chown(hba, st.st_uid, st.st_gid)
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
                    'hba_off': pgtls_hba_off, 'server_off': pgtls_server_off}[r['do']](r))
        out['ok'] = True
    except Refused as e:
        out['said'] = str(e)[:400]
    except Exception as e:                              # noqa: BLE001
        out['said'] = 'it went wrong: %s' % str(e)[:300]
    write_here(PGTLS_FILE, json.dumps(out))


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


def serve():
    d = web_fd()
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
        said_n, dh = nginx_part(r, last)
        out['dh'] = dict(out['dh'], **dh)
        said_v, keep = vip_part(r, last.get('applied') or {})
        said_f, fw = fw_part(r['fw'])
        out.update(state='done', said=[s for s in said_n + said_v + said_f if s], applied=keep,
                   fw=fw, access=access_now())
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
    return serve()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
