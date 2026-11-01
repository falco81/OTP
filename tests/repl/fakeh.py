from common import *
class D: pass
class H:
    def __init__(self, n):
        self.store = store(n)
        self.d = D(); self.d.tokens = otp.Tokens(self.store)
        self.d.fill_names_later = lambda names: None
    def me(self, role=None): return True
def act(n, a, name, **b):
    h = H(n)
    return otp._token_act(h, {'name': 'admin', 'role': 'fulladmin'}, b, a, name, 'admin')
