import sys, json; sys.argv=['otp']; __file__='/usr/local/lib/otp/otp.py'
exec(open('/usr/local/lib/otp/otp.py').read().replace("if __name__ == '__main__':","if False:"))
load_config(); st=Storage(open_db())
j=json.loads(st.get_meta('net:job:'+sys_node) if False else st.get_meta('net:job:nodeb') or '{}')
print('state', j.get('state'), 'boot', j.get('boot'), 'moved', j.get('moved'), 'bt', boot_time())
n=json.loads(st.get_meta('net:now:nodeb') or '{}'); print('now at', n.get('at'))
