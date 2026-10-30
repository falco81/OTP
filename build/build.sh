#!/bin/bash
set -e
cd /home/claude/build
mkdir -p out/otp-1.0.178
cat parts/00_head.py parts/10_totp_qr.py parts/20_db.py parts/30_ldap.py parts/40_radius_proto.py parts/41_reply_dict.py parts/50_storage.py parts/60_engine.py parts/60s_siem.py parts/65_codes.py parts/70_radius_server.py parts/72_guard.py parts/80_daemon.py parts/85_dbfiles.py parts/85k_dbkey.py parts/86_mail.py parts/86t_texts.py parts/86b_rbackup.py parts/86v_verify.py parts/87_ha.py parts/88_upgrade.py parts/88o_online.py parts/88p_proxy.py parts/88k_zipaes.py parts/88h_hisec.py parts/88d_downgrade.py parts/88w_web.py parts/88a_acme.py parts/87t_hatls.py parts/87u_readdress.py parts/87n_net.py parts/87x_trial.py parts/87m_ntp.py parts/87l_logs.py parts/87h_host.py parts/87q_ask.py parts/87d_dbtls.py parts/87i_isemontls.py parts/88z_alerts.py parts/89_rename.py parts/90_api.py parts/90m_mfa.py parts/90b_rbackup_api.py parts/90n_net_api.py parts/90h_host_api.py parts/90a_alerts_api.py parts/90p_metrics.py parts/96_console.py parts/95_cli.py > out/otp-1.0.178/otp.py
chmod 755 out/otp-1.0.178/otp.py
python3 -m py_compile out/otp-1.0.178/otp.py
