# 1.0.290: high availability with each node's database on a server of its own (layout B) - the
# steps on High availability -> Making it two.
S290 = {
    'This node’s name':
        'Jméno tohoto uzlu',
    'Every row is copied from this node’s server to the other one, both directions of replication set up.':
        'Všechny řádky se zkopírují ze serveru tohoto uzlu na druhý a nastaví se replikace oběma směry.',
    'Then on either node: the link between the two servers encrypted':
        'Pak na kterémkoli uzlu: zašifrování spojení mezi oběma servery',
    'Each node issues its database server’s certificate and its agent puts it in: verify-full, hostssl for the other server and the other node. High availability → Repair does the same.':
        'Každý uzel vydá certifikát svého databázového serveru a jeho agent ho nasadí: verify-full, hostssl pro druhý server a druhý uzel. Totéž udělá Vysoká dostupnost → Opravit.',
}
P290 = {}
