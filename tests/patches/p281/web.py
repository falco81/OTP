# 1.0.281 pages: the SNMP card offers OTP-MIB and the Zabbix 7.0 template - python3 web.py OUTDIR
import sys
O = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


edit('web/assets/admin.js', [(
"""  card.appendChild(el('p', 'muted small', 'The passphrases are not shown here - they are those set above (kept sealed). AES-256 is net-snmp\\'s AES256 and Zabbix\\'s AES256, not Cisco\\'s AES256C.'));
  host.appendChild(card);
}""",
"""  card.appendChild(el('p', 'muted small', 'The passphrases are not shown here - they are those set above (kept sealed). AES-256 is net-snmp\\'s AES256 and Zabbix\\'s AES256, not Cisco\\'s AES256C.'));
  /* Zabbix 7.0 (1.0.281): the template of every object, discovery, triggers, graphs and a dashboard. */
  card.appendChild(el('h3', 'peek-h', 'Zabbix 7.0'));
  var zp = el('p', 'note');
  zp.innerHTML = 'The template <b>otp by SNMP</b>: every object otp answers, the tables found by themselves (problems, certificates, nodes, file systems, directories, the replication), triggers, graphs and a dashboard of five pages. In Zabbix: <i>Data collection → Templates → Import</i>; then a host for each node - an SNMP interface at the node\\'s own address and port ' + d.port + ', SNMPv3, authPriv, ' + htmlText(d.auth || '') + ' and ' + htmlText(d.priv || '') + ', the security name and both passphrases above - and the template linked to it.';
  card.appendChild(zp);
  var zr = el('div', 'btnrow');
  [['zabbix', 'Download the Zabbix 7.0 template', 'download', 'primary'], ['mib', 'Download OTP-MIB', 'download', '']].forEach(function (x) {
    var b = cmdButton(x[1], x[2], x[3]);
    b.id = 'snmp-file-' + x[0];
    b.onclick = function () {
      busy(b, true);
      api('snmpfile&what=' + x[0]).then(function (r) {
        busy(b, false);
        var a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([r.text], {type: 'application/octet-stream'}));
        a.download = r.name;
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
        toast(r.name + ' is downloaded', 'good');
      }).catch(function (e) { busy(b, false); oops(e); });
    };
    zr.appendChild(b);
  });
  card.appendChild(zr);
  host.appendChild(card);
}""")])
print('web 1.0.281 patched')
edit('web/admin/index.php', [(
"""        'dbtls' => '/api/dbtls', 'metrics' => '/api/metrics', 'snmp' => '/api/snmp',
        'acme-push' => '/api/acme-push',
        'split' => '/api/split',
        'load' => '/api/load',""",
"""        'dbtls' => '/api/dbtls', 'metrics' => '/api/metrics', 'snmp' => '/api/snmp', 'snmpfile' => '/api/snmpfile',
        'acme-push' => '/api/acme-push',
        'split' => '/api/split',
        'load' => '/api/load',""")])
print('admin php 1.0.281 patched')
