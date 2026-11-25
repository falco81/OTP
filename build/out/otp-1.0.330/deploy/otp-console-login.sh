# The otp console when root signs in (otp 1.0.130).
# Switched with `otp --console-at-login on|off`; q in the console leaves it
# for this shell, and `otp --console` opens it again. Nothing happens for a
# command run over SSH, scp/sftp, a non-interactive shell, a shell opened
# from the console itself, or when OTP_NO_CONSOLE is set.
# For normal users too (1.0.240), those named by `otp --console-users` (or *):
# through sudo, with their own password - only who may become root with sudo
# gets it; anybody else is told so and keeps the ordinary shell.
if [ -n "${PS1:-}" ] && [ -t 0 ] && [ -t 1 ] && [ -z "${OTP_CONSOLE:-}" ] \
   && [ -z "${OTP_NO_CONSOLE:-}" ] && [ -z "${SSH_ORIGINAL_COMMAND:-}" ] \
   && [ -x /usr/local/bin/otp ] \
   && [ -f /etc/otp-console-login ] && [ ! -L /etc/otp-console-login ]; then
    if [ "$(id -u 2>/dev/null)" = "0" ]; then
        if [ "$(head -c 3 /etc/otp-console-login 2>/dev/null)" = "on" ]; then
            export OTP_CONSOLE=1
            /usr/local/bin/otp --console
        fi
    elif [ "$(id -u 2>/dev/null)" -ge 1000 ] 2>/dev/null; then
        _otp_users=" $(sed -n 's/^users: //p' /etc/otp-console-login 2>/dev/null | head -n 1) "
        _otp_me="$(id -un 2>/dev/null)"
        case "$_otp_users" in
            *" * "*|*" $_otp_me "*)
                export OTP_CONSOLE=1
                if id -Gn 2>/dev/null | tr ' ' '\n' | grep -qxE 'wheel|sudo|admin' \
                   || sudo -n true 2>/dev/null; then
                    echo "otp: the console - sudo asks for your password (Ctrl+C: the ordinary shell)"
                    sudo -p "[sudo] password for %p: " env OTP_CONSOLE=1 /usr/local/bin/otp --console
                else
                    echo "otp: the console is set to open for you, but it needs sudo rights (the wheel group) - the ordinary shell"
                fi
                ;;
        esac
        unset _otp_users _otp_me
    fi
fi
