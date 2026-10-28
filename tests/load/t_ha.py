import subprocess, time, json
def q(port, sql):
    r=subprocess.run(['su','postgres','-c','psql -p %d -d optmove -XAt -v ON_ERROR_STOP=1'%port],input=sql+';\n',capture_output=True,text=True)
    if r.returncode: print('ERR',port,r.stderr.strip()[:300])
    return r.stdout.strip()
A,B=5432,5433
subA=q(A,"SELECT subname FROM pg_subscription"); subB=q(B,"SELECT subname FROM pg_subscription")
def pause(): q(A,"ALTER SUBSCRIPTION %s DISABLE"%subA); q(B,"ALTER SUBSCRIPTION %s DISABLE"%subB)
def resume(): q(A,"ALTER SUBSCRIPTION %s ENABLE"%subA); q(B,"ALTER SUBSCRIPTION %s ENABLE"%subB); time.sleep(4)
def both(sql): return q(A,sql), q(B,sql)
# 1 dup meta
q(A,"DELETE FROM meta WHERE k='duptest'"); time.sleep(1)
pause(); q(A,"INSERT INTO meta(k,v) VALUES('duptest','from-a')"); q(B,"INSERT INTO meta(k,v) VALUES('duptest','from-b')"); resume()
print('1 dup meta:', both("SELECT v FROM meta WHERE k='duptest'"), both("SELECT pid IS NOT NULL FROM pg_stat_subscription"))
# 2 dup token name
q(A,"DELETE FROM tokens WHERE name='hatest@load.test'"); time.sleep(1)
pause()
q(A,'''INSERT INTO tokens(name,secret,state,last_step,scratch,scratch_left) VALUES('hatest@load.test','SA','active',0,'["c1","c2","c3"]',3)''')
q(B,"INSERT INTO tokens(name,secret,state,last_step,scratch,scratch_left) VALUES('hatest@load.test','SB','active',0,'[]',0)")
resume()
print('2 dup token:', both("SELECT id||' '||secret FROM tokens WHERE name='hatest@load.test'"), both("SELECT pid IS NOT NULL FROM pg_stat_subscription"))
# make same row on both: delete and recreate on A only
q(A,"DELETE FROM tokens WHERE name='hatest@load.test'"); time.sleep(2)
q(A,'''INSERT INTO tokens(name,secret,state,last_step,scratch,scratch_left) VALUES('hatest@load.test','SA','active',10,'["c1","c2","c3"]',3)'''); time.sleep(2)
print('   same:', both("SELECT secret||' '||state||' '||scratch FROM tokens WHERE name='hatest@load.test'"))
# 3 disable on A vs login write on B
pause(); q(A,"UPDATE tokens SET state='disabled' WHERE name='hatest@load.test'"); time.sleep(0.2)
q(B,"UPDATE tokens SET last_used=1, last_step=12, last_from='x' WHERE name='hatest@load.test'"); resume()
print('3 disable vs login:', both("SELECT state||' step='||last_step FROM tokens WHERE name='hatest@load.test'"))
# 4 concurrent scratch use
pause(); q(A,'''UPDATE tokens SET scratch='["c2","c3"]', scratch_left=2 WHERE name='hatest@load.test' ''')
q(B,'''UPDATE tokens SET scratch='["c1","c3"]', scratch_left=2 WHERE name='hatest@load.test' '''); resume()
print('4 scratch both used:', both("SELECT scratch||' '||scratch_left FROM tokens WHERE name='hatest@load.test'"))
# 5 new codes on A when empty
q(A,"UPDATE tokens SET scratch='[]', scratch_left=0 WHERE name='hatest@load.test'"); time.sleep(2)
q(A,'''UPDATE tokens SET scratch='["n1","n2"]', scratch_left=2 WHERE name='hatest@load.test' '''); time.sleep(2)
print('5 new codes:', both("SELECT scratch||' '||scratch_left FROM tokens WHERE name='hatest@load.test'"))
# 6 lock on A vs B login-row
pause(); q(A,"UPDATE tokens SET failures=10, locked_until=9999999999 WHERE name='hatest@load.test'"); time.sleep(0.2)
q(B,"UPDATE tokens SET last_from='y' WHERE name='hatest@load.test'"); resume()
print('6 lock kept:', both("SELECT failures||' '||coalesce(locked_until,0) FROM tokens WHERE name='hatest@load.test'"))
# 7 admin unlock on B later
q(B,"UPDATE tokens SET failures=0, locked_until=NULL WHERE name='hatest@load.test'"); time.sleep(2)
print('7 unlock:', both("SELECT failures||' '||coalesce(locked_until,0) FROM tokens WHERE name='hatest@load.test'"))
# 8 re-enable on B later than A's disable
q(B,"UPDATE tokens SET state='active' WHERE name='hatest@load.test'"); time.sleep(2)
print('8 enable:', both("SELECT state FROM tokens WHERE name='hatest@load.test'"))
q(A,"DELETE FROM tokens WHERE name='hatest@load.test'"); q(A,"DELETE FROM meta WHERE k='duptest'"); time.sleep(2)
print('end subs', both("SELECT pid IS NOT NULL FROM pg_stat_subscription"), both("SELECT count(*) FROM tokens WHERE name='hatest@load.test'"))
