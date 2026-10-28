from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
a=DummyAuthorizer(); a.add_user('rbtest','Rb-pass-123','/srv/rb-ftp',perm='elradfmwMT')
h=FTPHandler; h.authorizer=a; h.passive_ports=range(31200,31210)
FTPServer(('127.0.0.1',2121),h).serve_forever()
