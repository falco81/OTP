# 1.0.290: high availability with each node's database on a server of its own (layout B), through
# both nodes' otp-db-agent. The parts.   python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


# The other otp node / this node itself where it is the nodes' own (keepalived, the firewall, the
# clocks, the split's look at the other machine): ha_peer_node() / ha_own_node() - the same as
# ha_peer / ha_address without layout B. Asked only where they are defined: some tests run a part
# alone.
OTHER = "(ha_peer_node() if 'ha_peer_node' in globals() else CONFIG.get('ha_peer'))"
OWN = "(ha_own_node() if 'ha_own_node' in globals() else (CONFIG.get('ha_address') or node_address()))"

# ---- the command line ------------------------------------------------------------------------
edit('95_cli.py', [
(
"""    g.add_argument('--ha-peer-port', type=int, metavar='N', default=None,
                   help='the other node\\'s PostgreSQL port (5432)')
""",
"""    g.add_argument('--ha-peer-port', type=int, metavar='N', default=None,
                   help='the other node\\'s PostgreSQL port (5432)')
    g.add_argument('--ha-peer-node', metavar='ADDRESS', default=None,
                   help='with --ha-setup, each node\\'s database on a server of its own '
                        '(otp-db-agent): the other OTP NODE - --ha-peer is then the other '
                        'DATABASE server')
"""),
# --ha-setup / --ha-bundle: the replicated way for a database on this node's agent's server too
(
"""    if store.db.engine == 'postgres' and host0 in ('', 'localhost', '127.0.0.1', '::1') \\
            and not args.ha_shared and (args.ha_setup or CONFIG.get('ha_mode') == 'replicated'):""",
"""    if getattr(args, 'ha_peer_node', None) and not db_agent_here():
        # Only for a database on a server of its own (1.0.290): without one --ha-peer is the
        # other node, as ever.
        raise SystemExit('otp: --ha-peer-node is for a node whose database is on a server of its '
                         'own, looked after by otp-db-agent (otp --db-agent-join first) - here '
                         '--ha-peer is the other node')
    if store.db.engine == 'postgres' and (host0 in ('', 'localhost', '127.0.0.1', '::1') or
                                          db_agent_here()) \\
            and not args.ha_shared and (args.ha_setup or CONFIG.get('ha_mode') == 'replicated'):"""),
# firewall_peer: on the database server, by its agent
(
"""    try:
        a = peer_address(peer)
    except ValueError as e:
        print(pal.bad_line('the firewall: %s is not an address (%s)' % (peer, e)))
        return False
    ha_joining_set([str(a)], cli_who(), 'a cluster made with it')""",
"""    try:
        a = peer_address(peer)
    except ValueError as e:
        print(pal.bad_line('the firewall: %s is not an address (%s)' % (peer, e)))
        return False
    if db_agent_here():
        # Each node's database on a server of its own (1.0.290): the database's port is on that
        # server - its agent lets the other database server and the other otp node in there;
        # this node's own firewall lets the other otp node in, as a node being joined.
        other = str((db_agent() or {}).get('peer_node') or '') or str(a)
        ha_joining_set([other], cli_who(), 'a cluster made with it')
        ok_all = True
        try:
            got = db_agent_fw([str(a)] + [x for x in db_agent_link_peers() if x != str(a)])
            for line in got.get('said') or []:
                print(pal.ok_line('the database server: %s' % line))
        except ValueError as e:
            ok_all = False
            print(pal.bad_line('the database server\\'s firewall: %s' % e))
        print(pal.ok_line('this node\\'s firewall lets %s in (the other otp node)' % other))
        return ok_all
    ha_joining_set([str(a)], cli_who(), 'a cluster made with it')"""),
# --ha-setup, replicated
(
"""    port = int(CONFIG.get('db_port') or 5432)
    name, user, pw = CONFIG.get('db_name'), CONFIG.get('db_user'), CONFIG.get('db_password')
    try:
        restart, major = pg_prepare_local(port, peer, name, user, pw, say,
                                          own_address=args.ha_address or '')""",
"""    port = int(CONFIG.get('db_port') or 5432)
    name, user, pw = CONFIG.get('db_name'), CONFIG.get('db_user'), CONFIG.get('db_password')
    layout_b = db_agent_here()
    if layout_b:
        # Each node's database on a server of its own (1.0.290): --ha-peer is the other
        # DATABASE server, --ha-peer-node the other otp node - kept as peer_node, with this
        # node's own address toward it (node_address: ha_address is its database server).
        pn = str(getattr(args, 'ha_peer_node', None) or db_agent().get('peer_node') or '').strip()
        if not pn:
            pn = ask('The other otp node\\'s address (--ha-peer is the other database server)')
        if not pn:
            raise SystemExit('otp: the other otp node\\'s address is needed: --ha-peer-node ADDRESS '
                             '(--ha-peer %s is the other database server)' % peer)
        try:
            peer_address(pn)
        except ValueError as e:
            raise SystemExit('otp: --ha-peer-node: %s' % e)
        if peer_address(pn) == peer_address(peer):
            raise SystemExit('otp: --ha-peer and --ha-peer-node are one address - --ha-peer is the '
                             'other DATABASE server, --ha-peer-node the other otp node')
        port = int(db_agent().get('pg_port') or port)
        db_agent_put({'peer_node': pn, 'node_address': db_agent_my_address(pn)})
        say('the other otp node: %s; the other database server: %s; this node\\'s database: %s '
            '(otp-db-agent)' % (pn, peer, db_agent_db_host()))
    try:
        restart, major = pg_prepare_local(port, peer, name, user, pw, say,
                                          own_address=args.ha_address or '')"""),
(
"""    firewall_peer(peer, pal, port)
    if args.trusted_proxy:
        nginx_trusted_proxies(args.trusted_proxy, pal)
    me = args.ha_address or CONFIG.get('ha_address') or node_address()
    changes = {'ha_mode': 'replicated', 'ha_slot': 1, 'ha_peer': peer,""",
"""    firewall_peer(peer, pal, port)
    if args.trusted_proxy:
        nginx_trusted_proxies(args.trusted_proxy, pal)
    # Layout B (1.0.290): this node's address for the replication is its database server's.
    me = args.ha_address or CONFIG.get('ha_address') or (db_agent_db_host() if layout_b
                                                          else node_address())
    changes = {'ha_mode': 'replicated', 'ha_slot': 1, 'ha_peer': peer,"""),
(
"""            'peer': {'name': node_name(), 'address': me, 'port': port, 'slot': 1},
            'cluster': CONFIG.get('site_name') or 'otp'}
    phrase = ha_passphrase()
    target = Path(args.ha_bundle or '/root/otp-join-%s.json' % node_name())""",
"""            'peer': {'name': node_name(), 'address': me, 'port': port, 'slot': 1},
            'cluster': CONFIG.get('site_name') or 'otp'}
    if layout_b:
        # The node itself beside its database server (1.0.290): the other node's firewall,
        # keepalived and clocks take this one, its database server is only the replication's.
        data['peer']['node'] = ha_own_node()
    phrase = ha_passphrase()
    target = Path(args.ha_bundle or '/root/otp-join-%s.json' % node_name())"""),
(
"""    print('')
    print(pal.head('on the second node (%s)' % peer))
    print('  1. install the same version:   ./install.sh --with-db postgres --yes')""",
"""    print('')
    if layout_b:
        pn = ha_peer_node()
        print(pal.head('on the other database server (%s)' % peer))
        print('  ./install.sh --db-server postgres --otp-node %s --otp-node %s' % (pn, ha_own_node()))
        print('     (PostgreSQL 16 and otp-db-agent; it prints a join code)')
        print('')
        print(pal.head('on the second otp node (%s)' % pn))
        print('  1. install the same version:   ./install.sh --yes')
        print('  2. join its database server:   otp --db-agent-join -     (the code on standard input)')
        print('  3. copy the bundle over:       scp %s root@%s:/root/' % (target, pn))
        print('  4. join:                       otp --ha-join /root/%s --node-name NAME' % target.name)
        print('     Its database goes onto %s: every row copied from %s, both directions set up.'
              % (peer, db_agent_db_host()))
        print('  5. then on either node:        otp --ha-tls-repair   (the link between the two '
              'database servers encrypted, verify-full, through both agents)')
        return 0
    print(pal.head('on the second node (%s)' % peer))
    print('  1. install the same version:   ./install.sh --with-db postgres --yes')"""),
# --ha-join, replicated: the database goes onto this node's agent's server
(
"""    port = int(FILE_CONFIG.get('db_port') or 5432) if FILE_CONFIG.get('db_engine') == 'postgres' \\
        else 5432
    # What this node holds kept first, before anything is changed (1.0.249), as --ha-resync keeps""",
"""    port = int(FILE_CONFIG.get('db_port') or 5432) if FILE_CONFIG.get('db_engine') == 'postgres' \\
        else 5432
    here = '127.0.0.1'
    # This node's database onto its agent's server (1.0.290) when it joined one and its database
    # is not on another PostgreSQL already (one on this machine stays looked after by the root
    # helper, as without an agent).
    if db_agent_on() and (FILE_CONFIG.get('db_engine') != 'postgres' or
                          db_agent_is_target(FILE_CONFIG)):
        if str((db_agent() or {}).get('engine') or 'postgres') != 'postgres':
            raise SystemExit('otp: this node\\'s agent looks after MariaDB - a replicated cluster '
                             'needs PostgreSQL 16 on each database server')
        DBAGENT_STATE['target'] = True
        port = int(db_agent().get('pg_port') or port)
        here = db_agent_db_host()
        pn = str(peer.get('node') or peer.get('address') or '')
        # This node's own address beside it: ha_address is its database server.
        db_agent_put({'peer_node': pn, 'node_address': db_agent_my_address(pn)})
        if not args.ha_address:
            args.ha_address = here
        say('this node\\'s database goes onto %s (otp-db-agent); the other otp node: %s'
            % (here, pn))
    # What this node holds kept first, before anything is changed (1.0.249), as --ha-resync keeps"""),
(
"""        local = db_open({'db_engine': 'postgres', 'db_host': '127.0.0.1', 'db_port': port,
                         'db_name': name, 'db_user': user, 'db_password': pw})
        local.make_tables()""",
"""        local = db_open({'db_engine': 'postgres', 'db_host': here, 'db_port': port,
                         'db_name': name, 'db_user': user, 'db_password': pw})
        local.make_tables()"""),
(
"""    write_file_settings({'db_engine': 'postgres', 'db_host': '127.0.0.1', 'db_port': port,
                         'db_name': name, 'db_user': user, 'db_password': pw,
                         'node_name': node, 'ha_mode': 'replicated',""",
"""    write_file_settings({'db_engine': 'postgres', 'db_host': here, 'db_port': port,
                         'db_name': name, 'db_user': user, 'db_password': pw,
                         'node_name': node, 'ha_mode': 'replicated',"""),
(
"""    say('both directions replicate: this node -> %s and %s -> this node'
        % (peer.get('name'), peer.get('name')))
    if args.trusted_proxy:""",
"""    say('both directions replicate: this node -> %s and %s -> this node'
        % (peer.get('name'), peer.get('name')))
    if DBAGENT_STATE.get('target'):
        # The agent told the cluster's authorities now (1.0.290): this node joined it with an
        # authority of its own (standalone) - the other node's certificate on that server was
        # refused as another cluster's.
        try:
            ts = Storage(db_open({'db_engine': 'postgres', 'db_host': here, 'db_port': port,
                                  'db_name': name, 'db_user': user, 'db_password': pw}))
            try:
                if db_agent_trust_sync(ts, force=True):
                    say('the database agent knows the cluster\\'s authorities')
            finally:
                ts.db.close()
        except Exception as e:                          # noqa: BLE001
            print(pal.warn_line('the database agent was not told the cluster\\'s authorities: %s '
                                '- otp tells it once it runs' % str(e)[:200]))
        print(pal.dim('  The link between the two database servers: otp --ha-tls-repair '
                      '(verify-full, through both agents).'))
    if args.trusted_proxy:"""),
])

# ---- the bundle made again: the node itself beside its database server ------------------------
edit('87_ha.py', [
(
"""            'cluster': CONFIG.get('site_name') or 'otp'}
    data['db']['db_host'] = data['peer']['address']
    return data""",
"""            'cluster': CONFIG.get('site_name') or 'otp'}
    data['db']['db_host'] = data['peer']['address']
    if 'db_agent_layout_b' in globals() and db_agent_layout_b():
        # Layout B (1.0.290): the node itself, apart from its database server.
        data['peer']['node'] = ha_own_node()
    return data"""),
])

# ---- the clocks: the other otp node's, its database server's said as such -----------------------
edit('87m_ntp.py', [
(
"""    other = CONFIG.get('ha_peer') if CONFIG.get('ha_mode') else ''""",
"""    # The other otp node - not its database server in layout B (1.0.290).
    other = %s if CONFIG.get('ha_mode') else ''""" % OTHER),
])
edit('87z_clock.py', [
(
"""        conf = ha_peer_conf(timeout=2)
        name = next((n['name'] for n in ha_peer_rows(store)), 'the other node')""",
"""        conf = ha_peer_conf(timeout=2)
        name = next((n['name'] for n in ha_peer_rows(store)), 'the other node')
        if 'db_agent_layout_b' in globals() and db_agent_layout_b():
            # Layout B (1.0.290): ha_peer is the other DATABASE server, another machine than the
            # other node - its clock said as that server's, never taken for the node's (the
            # heartbeats are not corrected by it).
            name = CLOCK_PEER_DB % name"""),
(
"""CLOCK_DB_SERVER = 'the database server'""",
"""CLOCK_DB_SERVER = 'the database server'
CLOCK_PEER_DB = 'the database server of %s'     # layout B: the other node's own server (1.0.290)"""),
])

# ---- the split's look at the other machine ------------------------------------------------------
edit('87y_split.py', [
(
"""    host = str(CONFIG.get('ha_peer') or '').strip()
    if not host:
        return False""",
"""    host = str(%s or '').strip()     # the other node's machine (layout B: not its database server)
    if not host:
        return False""" % OTHER),
])

# ---- the VIP address and the firewall: the nodes' own -------------------------------------------
edit('88w_web.py', [
(
"""        cands = [vip_plain(CONFIG.get('ha_peer'), addr), vip_plain(vip_peer_seen(store), addr)]""",
"""        cands = [vip_plain(%s, addr), vip_plain(vip_peer_seen(store), addr)]""" % OTHER),
(
"""    peer = str(CONFIG.get('ha_peer') or '')
    if CONFIG.get('ha_mode') == 'shared':
        said = vip_peer_published(store, like)""",
"""    peer = str(%s or '')         # layout B (1.0.290): the other otp node
    if CONFIG.get('ha_mode') == 'shared':
        said = vip_peer_published(store, like)""" % OTHER),
(
"""               'own': vip_plain(CONFIG.get('ha_address') or node_address(), v.get('address')),""",
"""               # this node itself - not its database server in layout B (1.0.290)
               'own': vip_plain(%s, v.get('address')),""" % OWN),
(
"""        if node == me and CONFIG.get('ha_peer'):
            out.add(CONFIG['ha_peer'])
        if node != me:
            out.add(CONFIG.get('ha_address') or node_address())""",
"""        # The other otp node / this one (layout B, 1.0.290: not their database servers).
        other = %s
        if node == me and other:
            out.add(other)
        if node != me:
            out.add(%s)""" % (OTHER, OWN)),
])
edit('90_api.py', [
(
"""        return dict(_ha_view(h, me, nodes), db_admin=db_admin(), dbservers=db_agent_servers(h.store))""",
"""        # db_here (1.0.290): this node's database is on its agent's server - Making it two shows
        # the steps of layout B then.
        return dict(_ha_view(h, me, nodes), db_admin=db_admin(), dbservers=db_agent_servers(h.store),
                    db_here=db_agent_here())"""),
])
print('1.0.290 parts done')
