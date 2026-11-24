"""1.0.329 (deploy, OUTDIR): the database agent's databases and accounts are each one cluster's -
another cluster's node is refused them; ones there before are taken over only when they are
otp's kind (an account that owns no other database, a MariaDB account with rights on its own
database only, a database no other account has rights on)."""
import sys, pathlib
OUT = pathlib.Path(sys.argv[1])


def edit(path, pairs):
    p = pathlib.Path(path)
    s = p.read_text()
    for a, b in pairs:
        n = s.count(a)
        assert n == 1, (str(p), n, a[:90])
        s = s.replace(a, b)
    p.write_text(s)


edit(OUT / 'deploy/otp_db_agent.py', [
("""            try:
                owner = self.cert_op(op, args)
                mine = []
                if owner:
                    mine = self.issuers_now(node, der)
                    self.owner_check(node, mine)
                out = self.ops.run_op(op, args, self.c)
                out.pop('agent_restart', None)          # the agent's own word only
""",
 """            try:
                owner = self.cert_op(op, args)
                mine = []
                if owner:
                    mine = self.issuers_now(node, der)
                    self.owner_check(node, mine)
                names = self.names_of(op, args)
                if names:
                    mine = mine or self.issuers_now(node, der)
                    self.names_check(node, mine, names)
                out = self.ops.run_op(op, args, self.c)
                out.pop('agent_restart', None)          # the agent's own word only
                if names:
                    self.names_put(node, names, mine)
"""),
("""    def owner_put(self, node, args, mine=()):
""",
 """    # -- each database and account one cluster's (1.0.329) ----------------------------------
    # A node could name any database or account: on MariaDB it was given every right on another
    # application's database, or an account there had its password reset; on PostgreSQL a role
    # of the server's was given the node's password and let in from the network. Several
    # clusters may share one server (the certificate above is one cluster's already); now each
    # database and account is the cluster's whose node made it, known by its authority as the
    # certificate is. One there before (an agent before 1.0.329, or made by hand) is taken
    # over by the first cluster that asks for it - only when it is otp's kind, which the
    # operation itself checks on the server.
    NAME_FIELDS = {'pg_prepare': (('db', 'db'), ('user', 'user')),
                   'dbmake': (('db', 'name'), ('user', 'user')),
                   'pg_allow': (('db', 'db'), ('user', 'user')),
                   'my_allow': (('db', 'db'), ('user', 'user')),
                   'pg_publication': (('db', 'db'),),
                   'pgtls': (('db', 'db'), ('user', 'user'))}

    def names_of(self, op, args):
        if not isinstance(args, dict):
            return []
        out = []
        for kind, field in self.NAME_FIELDS.get(op, ()):
            v = str(args.get(field) or '').strip()
            if v:
                out.append((kind, v.lower()))
        return out

    def _names_path(self):
        return os.path.join(self.c['state'], 'names.json')

    def _same_cluster(self, rec, node, mine):
        \"\"\"Whether `node` (signed by `mine`) is of the cluster a record is of - as owner_check
        decides it for the server's certificate. A record whose node is gone (left, forgotten,
        not heard from for 30 days) is anybody's.\"\"\"
        if not rec.get('node') or rec.get('node') == node:
            return True
        with self.lock:
            cl = clients(self.c)
        owner = next((x for x in cl if x.get('name') == rec['node']), None)
        if owner is None or stale(owner):
            return True
        theirs = set(rec.get('issuers') or []) | set(rec.get('cas') or []) | \\
            set(owner.get('issuers') or []) | set(self._cas_of(owner.get('ca')))
        if theirs & set(mine or []):
            return True
        verified = set(rec.get('issuers') or []) | set(owner.get('issuers') or [])
        asking = next((x for x in cl if x.get('name') == node), None) or {}
        return bool(verified & set(issuers_seen(asking)))

    def names_check(self, node, mine, names):
        rec = _json(self._names_path(), {})
        rec = rec if isinstance(rec, dict) else {}
        for kind, name in names:
            one = (rec.get(kind) or {}).get(name)
            if isinstance(one, dict) and not self._same_cluster(one, node, mine):
                raise self.ops.Refused(
                    'the %s %s on this server is %s\\'s, of another authority (another cluster) - '
                    'not given to %s; choose another name, or take %s away here first '
                    '(otp_db_agent.py --forget %s)' % ('database' if kind == 'db' else 'account', name,
                                                       one['node'], node, one['node'], one['node']))

    def names_put(self, node, names, mine):
        with self.lock:
            one = next((x for x in clients(self.c) if x.get('name') == node), None) or {}
        try:
            rec = _json(self._names_path(), {})
            rec = rec if isinstance(rec, dict) else {}
            changed = False
            for kind, name in names:
                had = (rec.setdefault(kind, {})).get(name)
                if isinstance(had, dict) and had.get('node') == node and \\
                        set(had.get('issuers') or []) >= set(mine or []):
                    continue
                rec[kind][name] = {'node': node, 'issuers': list(mine or []),
                                   'cas': self._cas_of(one.get('ca')), 'at': time.time()}
                changed = True
            if changed:
                os.makedirs(self.c['state'], mode=0o700, exist_ok=True)
                _write(self._names_path(), json.dumps(rec))
        except OSError:
            pass

    def owner_put(self, node, args, mine=()):
"""),
])

edit(OUT / 'deploy/otp_pg_ops.py', [
("""    sql(conf, quiet + '%s ROLE "%s" WITH LOGIN PASSWORD %s' % ('ALTER' if have else 'CREATE', user,
""",
 """    pg_owns_only(conf, user, db, have)
    sql(conf, quiet + '%s ROLE "%s" WITH LOGIN PASSWORD %s' % ('ALTER' if have else 'CREATE', user,
"""),
("""def op_pg_allow(args, conf):
    \"\"\"pg_hba.conf lets these addresses into otp's database (an otp node, the other
    database server), host - hostssl once the link's TLS is on (pgtls hba).\"\"\"
    db = name_checked(args.get('db'), 'the database')
    user = name_checked(args.get('user'), 'the account')
    peers = addresses_checked(args.get('peers'), 'the addresses let in')
""",
 """def pg_owns_only(conf, user, db, have=None):
    \"\"\"An account there already taken by otp only when it is otp's kind (1.0.329): it owns no
    database but `db`, and `db` (when there) is its - otp's own account never owns another; an
    application's account that does (or whose database this is) is not handed to a node.\"\"\"
    if have is None:
        have = sql(conf, 'SELECT 1 FROM pg_roles WHERE rolname = %s' % W.pg_lit(user)) == '1'
    if have:
        other = sql(conf, "SELECT string_agg(datname, ', ') FROM pg_database d JOIN pg_roles r "
                          "ON r.oid = d.datdba WHERE r.rolname = %s AND d.datname <> %s"
                    % (W.pg_lit(user), W.pg_lit(db)))
        if other.strip():
            raise Refused('the account %s is there and owns other databases (%s) - not taken '
                          'over; choose another name' % (user, other.strip()))
    owner = sql(conf, 'SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s'
                % W.pg_lit(db))
    if owner and owner != user:
        raise Refused('the database %s is there, owned by %s - not taken over' % (db, owner))


def op_pg_allow(args, conf):
    \"\"\"pg_hba.conf lets these addresses into otp's database (an otp node, the other
    database server), host - hostssl once the link's TLS is on (pgtls hba).\"\"\"
    db = name_checked(args.get('db'), 'the database')
    user = name_checked(args.get('user'), 'the account')
    peers = addresses_checked(args.get('peers'), 'the addresses let in')
    pg_owns_only(conf, user, db)
"""),
("""    peers = addresses_checked(args.get('peers'), 'the addresses let in')
    if not peers:
        return {'said': ['no address given']}
    sqls = ['SET SESSION sql_log_off = 1;']
""",
 """    peers = addresses_checked(args.get('peers'), 'the addresses let in')
    if not peers:
        return {'said': ['no address given']}
    my_owns_only(conf, user, db)
    sqls = ['SET SESSION sql_log_off = 1;']
"""),
("""    sqls = ['SET SESSION sql_log_off = 1;',
            'CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;' % name]
""",
 """    my_owns_only(conf, user, name)
    sqls = ['SET SESSION sql_log_off = 1;',
            'CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;' % name]
"""),
("""# ---- MariaDB ----------------------------------------------------------------------------
def my_prog():
""",
 """# ---- MariaDB ----------------------------------------------------------------------------
MY_GRANT_RE = re.compile(r'^GRANT (.+?) ON (\\S+) TO ')


def my_owns_only(conf, user, db):
    \"\"\"An account or a database there already taken by otp only when it is otp's kind
    (1.0.329): the account has rights on `db` alone (and USAGE - none) at every host it is
    at; no other account has rights on `db`. ALTER USER and GRANT ALL gave a node another
    application's account, or every right on its database.\"\"\"
    hosts = [h for h in my_sql(conf, "SELECT Host FROM mysql.user WHERE User = '%s';" % user).split('\\n')
             if h.strip()]
    for h in hosts:
        if "'" in h or '\\\\' in h:
            raise Refused('the account %s is there at a host otp does not read (%r)' % (user, h))
        for line in my_sql(conf, "SHOW GRANTS FOR '%s'@'%s';" % (user, h)).split('\\n'):
            line = line.strip()
            if not line:
                continue
            m = MY_GRANT_RE.match(line)
            on = m.group(2).replace('\\\\', '') if m else ''
            if m and ((on == '*.*' and m.group(1).strip().upper() == 'USAGE') or
                      on in ('`%s`.*' % db, '%s.*' % db)):
                continue
            raise Refused('the account %s is there with rights beyond the database %s (%s) - not '
                          'taken over; choose another name' % (user, db, line[:120]))
    others = my_sql(conf, "SELECT DISTINCT CONCAT(User, '@', Host) FROM mysql.db WHERE "
                          "REPLACE(Db, '\\\\\\\\', '') = '%s' AND User <> '%s';" % (db, user))
    if others.strip():
        raise Refused('the database %s is there and other accounts have rights on it (%s) - not '
                      'taken over; choose another name' % (db, ', '.join(others.split())[:200]))


def my_prog():
"""),
])
