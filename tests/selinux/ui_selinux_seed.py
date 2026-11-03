import sys, json, time
WHICH = sys.argv[1] if len(sys.argv) > 1 else 'a'
sys.path.insert(0, '/usr/local/lib/otp'); sys.argv = ['x']
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db())
which = WHICH
LAB = [{'path': '/run/otp', 'label': 'httpd_var_run_t', 'want': 'httpd_var_run_t', 'why': 'the folder of the API token', 'ok': True},
       {'path': '/run/otp/api-token', 'label': 'var_run_t', 'want': 'httpd_var_run_t', 'why': 'the API token the pages read', 'ok': False},
       {'path': '/var/www/otp', 'label': 'httpd_sys_content_t', 'want': 'httpd_sys_content_t', 'why': 'the pages', 'ok': True},
       {'path': '/usr/libexec/keepalived/otp-vip-check', 'label': 'keepalived_unconfined_script_exec_t', 'want': 'keepalived_unconfined_script_exec_t', 'why': "keepalived's check of this node", 'ok': True}]
BO = [{'name': 'httpd_can_network_connect', 'why': 'the pages ask the daemon on 127.0.0.1:9861', 'on': True},
      {'name': 'authlogin_radius', 'why': 'SSH asks otp for the code', 'on': False}]
PO = [{'port': 18129, 'proto': 'udp', 'type': 'radius_port_t', 'why': 'SSH asks otp for the code on this port', 'labelled': False}]
DEN = {'tool': True, 'total': 14, 'groups': [
    {'source': 'httpd_t', 'target': 'var_run_t', 'class': 'file', 'perms': 'read', 'count': 11, 'what': 'php-fpm api-token', 'permissive': True},
    {'source': 'sshd_t', 'target': 'unreserved_port_t', 'class': 'udp_socket', 'perms': 'name_connect', 'count': 3, 'what': 'sshd', 'permissive': True}]}
perm = {'mode': 'Permissive', 'config': 'permissive', 'policy': 'targeted', 'relabel_pending': False, 'cmdline_off': False,
        'tools': {}, 'module': True, 'labels': LAB, 'booleans': BO, 'ports': PO, 'denials': DEN, 'ready': False,
        'problems': ['/run/otp/api-token is labelled var_run_t, not httpd_var_run_t (the API token the pages read)',
                     'the boolean authlogin_radius is off (SSH asks otp for the code)',
                     'port 18129/udp is not labelled radius_port_t (SSH asks otp for the code on this port)',
                     'SELinux refused 14 thing(s) since the machine started']}
good = dict(perm, mode='Enforcing', config='enforcing', labels=[dict(x, label=x['want'], ok=True) for x in LAB],
            booleans=[dict(x, on=True) for x in BO], ports=[dict(x, labelled=True) for x in PO],
            denials={'tool': True, 'total': 0, 'groups': []}, problems=[], ready=False)
dis = {'mode': 'Disabled', 'config': 'permissive', 'policy': 'targeted', 'relabel_pending': True, 'cmdline_off': False,
       'module': None, 'labels': [], 'booleans': [], 'ports': [], 'denials': {'tool': False, 'total': 0, 'groups': []},
       'problems': [], 'ready': False}
dis0 = dict(dis, config='disabled', relabel_pending=False)
now = time.time()
if which == 'a':
    st.set_meta('host:selinux:now:vm', json.dumps({'data': perm, 'at': now, 'done': 'x', 'error': '', 'said': [], 'action': 'check'}))
    st.set_meta('node:otp2', json.dumps({'at': now, 'version': otp.__version__, 'address': '10.99.9.2', 'host': 'otp2'}))
    st.set_meta('host:selinux:now:otp2', json.dumps({'data': good, 'at': now, 'done': 'y', 'error': '', 'said': ['SELinux is enforcing, and stays so after a restart'], 'action': 'enforce'}))
elif which == 'b':
    st.set_meta('host:selinux:now:vm', json.dumps({'data': dis0, 'at': now, 'done': 'x', 'error': '', 'said': [], 'action': 'check'}))
    st.set_meta('node:otp2', json.dumps({'at': now, 'version': otp.__version__, 'address': '10.99.9.2', 'host': 'otp2'}))
    st.set_meta('host:selinux:now:otp2', json.dumps({'data': dis, 'at': now, 'done': 'y', 'error': '', 'said': ['the files are labelled at the next start of the machine', 'restart the machine - it comes up permissive'], 'action': 'prepare'}))
elif which == 'off':
    for k in ('host:selinux:now:vm', 'host:selinux:now:otp2', 'node:otp2', 'host:selinux:want:vm'):
        st.db.run('DELETE FROM meta WHERE k = ?', (k,))
print('seeded', which)
