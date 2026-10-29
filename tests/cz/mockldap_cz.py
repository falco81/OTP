# The mock directory of test/mockldap.py with a Czech domain beside it:
# diacritics in OUs, groups, names, display names, a sAMAccountName and a UPN
# with them, a comma inside a CN (escaped in the DN), and a nested group.
# Usage: python3 mockldap_cz.py PACKAGE_DIR PORT
import sys, threading
sys.path.insert(0, sys.argv[1] + '/test')
import mockldap as m

B = 'DC=corpnet,DC=loc'
U = 'OU=Uživatelé,OU=Česká Lípa,' + B
G = 'OU=Skupiny – VPN,' + B
CZ_PEOPLE = {
    'CN=Jiří Čermák,' + U: {'sAMAccountName': ['jcermak'], 'userPrincipalName': ['jcermak@corpnet.cz'],
                            'displayName': ['Jiří Čermák'], 'mail': ['jiri.cermak@corpnet.cz'],
                            'mobile': ['+420 603 111 222'], '_password': 'Heslo-Žluťoučký-1'},
    'CN=Žofie Řeháková,' + U: {'sAMAccountName': ['žofie'], 'userPrincipalName': ['žofie@corpnet.cz'],
                               'displayName': ['Žofie Řeháková'], 'mail': ['zofie@corpnet.cz'],
                               '_password': 'Heslo-Ďábel-2'},
    'CN=Novák\\, Petr,' + U: {'sAMAccountName': ['pnovak'], 'userPrincipalName': ['pnovak@corpnet.cz'],
                              'displayName': ['Novák, Petr'], '_password': 'Heslo-Čárka-3'},
    'CN=Ondřej Šťastný,' + U: {'sAMAccountName': ['ostastny'], 'userPrincipalName': ['ostastny@corpnet.cz'],
                               'displayName': ['Ondřej Šťastný'], '_password': 'Heslo-Vnořený-4'},
    'CN=Łukasz Wójcik,' + U: {'sAMAccountName': ['łukasz'], 'userPrincipalName': ['łukasz@corpnet.cz'],
                               'displayName': ['Łukasz Wójcik'], '_password': 'Haslo-Łódź-6'},
    'CN=Иван Петров,' + U: {'sAMAccountName': ['иван'], 'userPrincipalName': ['иван@corpnet.cz'],
                            'displayName': ['Иван Петров'], '_password': 'Пароль-7'},
    'CN=Cizí Člověk,' + U: {'sAMAccountName': ['cizi'], 'userPrincipalName': ['cizi@corpnet.cz'],
                            'displayName': ['Cizí Člověk'], '_password': 'Heslo-Cizí-5'},
}
CZ_GROUPS = {
    'CN=Uživatelé VPN,' + G: {'cn': ['Uživatelé VPN'], 'sAMAccountName': ['Uživatelé VPN'],
                              'member': ['CN=Jiří Čermák,' + U, 'CN=Žofie Řeháková,' + U,
                                         'CN=Novák\\, Petr,' + U, 'CN=Dodavatelé – externí,' + G,
                                         'CN=Łukasz Wójcik,' + U, 'CN=Иван Петров,' + U]},
    'CN=Dodavatelé – externí,' + G: {'cn': ['Dodavatelé – externí'],
                                     'sAMAccountName': ['Dodavatelé – externí'],
                                     'member': ['CN=Ondřej Šťastný,' + U]},
    'CN=Správci OTP,' + G: {'cn': ['Správci OTP'], 'sAMAccountName': ['Správci OTP'],
                            'member': ['CN=Jiří Čermák,' + U, 'CN=Žofie Řeháková,' + U,
                                       'CN=Łukasz Wójcik,' + U]},
    'CN=Čtenáři,' + G: {'cn': ['Čtenáři'], 'sAMAccountName': ['Čtenáři'],
                        'member': ['CN=Novák\\, Petr,' + U]},
}
for dn, a in CZ_PEOPLE.items():
    a.setdefault('objectClass', ['top', 'person', 'organizationalPerson', 'user'])
    a.setdefault('userAccountControl', ['512'])
    a['memberOf'] = [g for g, ga in CZ_GROUPS.items() if dn in ga['member']]
for dn, a in CZ_GROUPS.items():
    a.setdefault('objectClass', ['top', 'group'])
    a['memberOf'] = [g for g, ga in CZ_GROUPS.items() if dn in ga['member']]
m.PEOPLE.update(CZ_PEOPLE)
m.GROUPS.update(CZ_GROUPS)
port, stop = m.serve(int(sys.argv[2]))
print('mock AD with Czech names on %d' % port, flush=True)
threading.Event().wait()
