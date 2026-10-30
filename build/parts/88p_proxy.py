

# ---- going out through a proxy (1.0.166) --------------------------------------------
# Settings → Proxy: what otp asks of the web itself - the new versions, the SMS
# gateway - and, handed to the root helper in its request (never on a command
# line), dnf or apt fetching the system updates. Mail, Active Directory, the
# database, syslog and the other node never go through it.
def proxy_on(purpose='web'):
    if not CONFIG.get('proxy') or not str(CONFIG.get('proxy_url') or '').strip():
        return False
    if purpose == 'sms':
        return bool(CONFIG.get('proxy_sms', 1))
    if purpose == 'os':
        return bool(CONFIG.get('proxy_os', 1))
    return True


def proxy_full(purpose='web'):
    """The proxy's address with its user and password in it, for urllib, dnf
    and apt - '' where none is to be used. Never logged, never shown."""
    if not proxy_on(purpose):
        return ''
    url = str(CONFIG.get('proxy_url') or '').strip().rstrip('/')
    user = str(CONFIG.get('proxy_user') or '').strip()
    if not user:
        return url
    pw = unseal_secret(CONFIG.get('proxy_password') or '') or ''
    scheme, _, rest = url.partition('://')
    return '%s://%s:%s@%s' % (scheme, urllib.parse.quote(user, safe=''),
                              urllib.parse.quote(pw, safe=''), rest)


def proxy_no_list():
    return [w.strip().lower() for w in re.split(r'[\s,;]+', str(CONFIG.get('proxy_no') or ''))
            if w.strip()]


def proxy_skips(host):
    """Whether this host is reached straight, as proxy_no says."""
    host = str(host or '').strip('[]').lower()
    if not host:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    for one in proxy_no_list():
        if one == '*':
            return True
        if ip is not None and ('/' in one or re.match(r'^[0-9a-f.:]+\Z', one)):
            try:
                if ip in ipaddress.ip_network(one.strip('[]'), strict=False):
                    return True
            except ValueError:
                pass
            continue
        one = one.lstrip('*')
        if one.startswith('.'):
            if host.endswith(one) or host == one[1:]:
                return True
        elif host == one:
            return True
    return False


class _ProxyOnly(urllib.request.ProxyHandler):
    """ProxyHandler without its look at no_proxy in the environment: only
    proxy_no says what goes straight."""
    def proxy_open(self, req, proxy, type):
        proxy_type, user, password, hostport = urllib.request._parse_proxy(proxy)
        if user and password:
            creds = base64.b64encode(('%s:%s' % (urllib.parse.unquote(user),
                                                 urllib.parse.unquote(password))).encode())
            req.add_header('Proxy-authorization', 'Basic ' + creds.decode('ascii'))
        req.set_proxy(urllib.parse.unquote(hostport), proxy_type or req.type)
        return None


def url_open(req, timeout=30, context=None, purpose='web'):
    """urllib.request.urlopen, through the proxy where one is set and the host
    is not one reached straight; never through what the environment says."""
    if not isinstance(req, urllib.request.Request):
        req = urllib.request.Request(req)
    proxy = proxy_full(purpose)
    host = urllib.parse.urlsplit(req.full_url).hostname or ''
    handlers = [_ProxyOnly(
        {'http': proxy, 'https': proxy} if proxy and not proxy_skips(host) else {})]
    if context is not None:
        handlers.append(urllib.request.HTTPSHandler(context=context))
    return urllib.request.build_opener(*handlers).open(req, timeout=timeout)


def proxy_try(url=''):
    """Settings → Proxy → Try it: a page fetched through the proxy, and what came
    back or what stopped it."""
    if not proxy_on():
        raise ValueError('no proxy is set - switch it on and give its address first')
    url = str(url or '').strip() or online_url() or 'https://github.com/'
    if not re.match(r'^https?://[^\s]+\Z', url):
        raise ValueError('an address starting https://')
    began = time.time()
    host = urllib.parse.urlsplit(url).hostname or ''
    req = urllib.request.Request(url, method='HEAD', headers={
        'User-Agent': 'otp/%s (+proxy check)' % __version__})
    try:
        with url_open(req, timeout=15, context=ssl.create_default_context()) as r:
            status = r.status
    except urllib.error.HTTPError as e:
        status = e.code
        if e.code == 407:
            return {'ok': False, 'url': url, 'status': 407,
                    'said': 'the proxy asks for a user name and a password (407) - they are '
                            'missing or wrong', 'ms': int((time.time() - began) * 1000)}
    except (OSError, ssl.SSLError, ValueError) as e:
        said = str(getattr(e, 'reason', '') or e)
        if 'Tunnel connection failed: 407' in said:
            said = 'the proxy asks for a user name and a password (407) - they are missing or wrong'
        return {'ok': False, 'url': url, 'said': said[:300],
                'ms': int((time.time() - began) * 1000)}
    return {'ok': True, 'url': url, 'status': status, 'straight': proxy_skips(host),
            'ms': int((time.time() - began) * 1000)}
