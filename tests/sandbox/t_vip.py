import sys; sys.argv=['x','none']
exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
for b in ({'action':'vip_mode','mode':'stays'},{'action':'vip_move','to':'nodeb'},{'action':'vip_mode','mode':'back','prefer':'nodeb'},{'action':'vip_mode','mode':'back','prefer':'nodea2'}):
    print(call('web',b))
    v=call('web')['vip']; print('  ', v.get('mode'), v.get('prefer'), v.get('prefer_now'), v.get('move_to'))
