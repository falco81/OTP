from common import *
A, B = dbs()
for d in (A, B):
    d.make_tables()
import subprocess
for port, name in ((5432, 'hunt8r_a'), (5433, 'hunt8r_b')):
    subprocess.run(["true"]) if subprocess.run(["runuser","-u","postgres","--","psql","-p",str(port),"-d",name,"-qAtc","select 1 from pg_publication where pubname='otp_pub'"],capture_output=True,text=True).stdout.strip()=="1" else subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', str(port), '-d', name, '-qAtc',
                    "CREATE PUBLICATION otp_pub FOR ALL TABLES WITH (publish = 'insert, update, delete')"], check=True)
otp.ha_sequences(A, 1); otp.ha_sequences(B, 2)
otp.ha_subscribe(B, 'hunt8r_from_1', otp.ha_conninfo('127.0.0.1', 5432, 'hunt8r_a', 'hunt8r_otp', PW), copy_data=True)
otp.ha_subscribe(A, 'hunt8r_from_2', otp.ha_conninfo('127.0.0.1', 5433, 'hunt8r_b', 'hunt8r_otp', PW), copy_data=False)
otp.ha_wait_copied(B, 'hunt8r_from_1', print, 60)
print(health())
