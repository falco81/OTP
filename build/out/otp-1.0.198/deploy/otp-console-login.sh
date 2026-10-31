# The otp console when root signs in (otp 1.0.130).
# Switched with `otp --console-at-login on|off`; q in the console leaves it
# for this shell, and `otp --console` opens it again. Nothing happens for a
# command run over SSH, scp/sftp, a non-interactive shell, a shell opened
# from the console itself, or when OTP_NO_CONSOLE is set.
if [ -n "${PS1:-}" ] && [ -t 0 ] && [ -t 1 ] && [ -z "${OTP_CONSOLE:-}" ] \
   && [ -z "${OTP_NO_CONSOLE:-}" ] && [ -z "${SSH_ORIGINAL_COMMAND:-}" ] \
   && [ "$(id -u 2>/dev/null)" = "0" ] && [ -x /usr/local/bin/otp ] \
   && [ -f /etc/otp-console-login ] && [ ! -L /etc/otp-console-login ] \
   && [ "$(head -c 3 /etc/otp-console-login 2>/dev/null)" = "on" ]; then
    export OTP_CONSOLE=1
    /usr/local/bin/otp --console
fi
