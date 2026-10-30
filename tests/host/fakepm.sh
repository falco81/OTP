#!/bin/sh
# A package manager that changes nothing, for tests/host: check, upgrade, needs-restart.
case "$1" in
  check) echo "bash 5.2.26-1"; echo "kernel 6.8.0-49"; echo "openssl 3.0.13-0ubuntu3.4" ;;
  upgrade)
    [ "$2" = security ] && echo "Only the security updates (--security)"
    echo "Dependencies resolved."; echo "Downloading Packages:"; sleep 1
    for i in 1 2 3; do echo "  Upgrading        : pkg$i 1.0-$i  $i/3"; sleep 1; done
    for i in 1 2 3; do echo "  Verifying        : pkg$i 1.0-$i  $i/3"; sleep 0.3; done
    echo "Complete!" ;;
  needs-restart) echo "Reboot is required to fully utilize these updates."; exit 1 ;;
esac
exit 0
