"""1.0.332 (parts): the alert of a certificate running out measured by its life (short-lived ACME
certificates); the second (ECDSA) certificate watched, and not given to nginx once run out."""
import sys, pathlib
P = pathlib.Path(sys.argv[1])


def edit(name, pairs):
    p = P / name
    s = p.read_text()
    for a, b in pairs:
        n = s.count(a)
        assert n == 1, (name, n, a[:90])
        s = s.replace(a, b)
    p.write_text(s)


edit('88w_web.py', [
("""        alt = tls_alt(prof)
        if alt:
            out['alt'] = {'cert': alt['cert'], 'chain': alt.get('chain') or '',
                          'key': unseal_secret(alt['key'], 'web:tls')}
""",
 """        alt = tls_alt(prof)
        if alt and tls_alt_ran_out(alt):
            # Not given to nginx once run out (1.0.332): it went on offering it to every client
            # that takes ECDSA - most browsers - while the RSA one was good.
            alt = None
        if alt:
            out['alt'] = {'cert': alt['cert'], 'chain': alt.get('chain') or '',
                          'key': unseal_secret(alt['key'], 'web:tls')}
"""),
("""def tls_resolved(prof):
""",
 """def tls_alt_ran_out(alt, now=None):
    \"\"\"Whether the second certificate has run out (1.0.332).\"\"\"
    info = (alt or {}).get('info') or {}
    end = info.get('not_after')
    if not end:
        try:
            end = (cert_info(PEM_CERT.search(alt.get('cert') or '').group(0)) or {}).get('not_after')
        except (AttributeError, ValueError, TypeError):
            end = None
    try:
        return bool(end) and float(end) < (time.time() if now is None else now)
    except (TypeError, ValueError):
        return False


def tls_resolved(prof):
"""),
("""NGINX_CERT_FILES = {'node': os.path.join(_NGINX_CERT_DIR, 'otp.pem'),
""",
 """# The second (ECDSA) ones too (1.0.332): what root writes beside them.
NGINX_ALT_FILES = {'node': os.path.join(_NGINX_CERT_DIR, 'otp-ecdsa.pem'),
                   'vip': os.path.join(_NGINX_CERT_DIR, 'otp-vip-ecdsa.pem')}
NGINX_CERT_FILES = {'node': os.path.join(_NGINX_CERT_DIR, 'otp.pem'),
"""),
("""    return {'cert_now': cert_now(NGINX_CERT_FILES['node'], _root(node_name())),
""",
 """    # The second certificate, where the profile has one (1.0.332): the file stays when it is
    # taken away, so read only while it is the profile's.
    def _alt(target):
        try:
            prof = tls_profile(store, target) or {}
            if not tls_alt(prof):
                return None
            return cert_now(NGINX_ALT_FILES[target if target == 'vip' else 'node'], _root(target))
        except Exception:                               # noqa: BLE001
            return None
    return {'alt_cert_now': _alt(node_name()), 'vip_alt_cert_now': _alt('vip'),
            'cert_now': cert_now(NGINX_CERT_FILES['node'], _root(node_name())),
"""),
])

edit('88z_alerts.py', [
("""            for what, c in (('node', web.get('cert_now')), ('vip', web.get('vip_cert_now'))):
""",
 """            for what, c in (('node', web.get('cert_now')), ('vip', web.get('vip_cert_now')),
                            ('node-ecdsa', web.get('alt_cert_now')),
                            ('vip-ecdsa', web.get('vip_alt_cert_now'))):
"""),
("""                if what == 'vip' and fp in seen:
                    continue
                seen.add(fp)
                left = (float(c['not_after']) - now) / 86400
                if left < days:
                    who = _al(lang, 'VIP adresy', 'the VIP address') if what == 'vip' else n
                    add('cert:%s:%s' % (what, n if what == 'node' else 'vip'),
                        'bad' if left < 7 else 'warn', n if what == 'node' else '',
""",
 """                if what.startswith('vip') and fp in seen:
                    continue
                seen.add(fp)
                left = (float(c['not_after']) - now) / 86400
                # By its life (1.0.332): a certificate of 6 days (ACME's "shortlived") has fewer
                # than 21 left all its life - the alert was raised, and "bad", for good. A quarter
                # of its life, past where ACME renews it (a third).
                want, worst = days, 7
                try:
                    life = (float(c['not_after']) - float(c.get('not_before') or 0)) / 86400
                except (TypeError, ValueError):
                    life = 0
                if c.get('not_before') and 0 < life < 4 * days:
                    want = life / 4
                    worst = min(7, life / 8)
                if left < want:
                    who = _al(lang, 'VIP adresy', 'the VIP address') if what.startswith('vip') else n
                    if what.endswith('-ecdsa'):
                        who += ' (ECDSA)'
                    add('cert:%s:%s' % (what, n if not what.startswith('vip') else 'vip'),
                        'bad' if left < worst else 'warn', n if not what.startswith('vip') else '',
"""),
])
