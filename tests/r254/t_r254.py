"""t_r254.py - 1.0.254: the passkey checks of the server (t_webauthn.py)."""
import subprocess, sys, os
d = os.path.dirname(os.path.abspath(__file__))
r = subprocess.run([sys.executable, os.path.join(d, 't_webauthn.py')], capture_output=True, text=True)
print(r.stdout[-4000:])
sys.exit(r.returncode)
