# 1.0.276: the certificate sign-in's port against the balancer's own port, both ways.
S276 = {
    "the pages' own port": 'vlastní port stránek',
    "the balancer's own port (web_proxy_port)": 'vlastní port balanceru (web_proxy_port)',
    'Where nginx asks the browser for a certificate (8443: SELinux lets nginx have it already) - a port of its own, not the balancer’s own port (web_proxy_port). Opened in the firewall for the administrators’ networks.':
        'Kde nginx žádá prohlížeč o certifikát (8443: SELinux ho nginx už dovoluje) – vlastní port, ne vlastní port balanceru (web_proxy_port). Ve firewallu se otevře pro sítě administrátorů.',
}
P276 = {
    "web_proxy_port: {0} is the certificate sign-in's own port (admin_cert_port) - give the balancer another one ({1}, say)":
        'web_proxy_port: {0} je vlastní port přihlášení certifikátem (admin_cert_port) – zadejte balanceru jiný (třeba {1})',
    'admin_cert_port: {0} is {1} - give the certificate sign-in a port of its own ({2}, say)':
        'admin_cert_port: {0} je {1} – zadejte přihlášení certifikátem vlastní port (třeba {2})',
    'admin_cert_port: something on this node listens on {0} already - give a free port ({1}, say)':
        'admin_cert_port: na {0} už na tomto nodu něco naslouchá – zadejte volný port (třeba {1})',
}
