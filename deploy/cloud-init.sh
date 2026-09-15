#!/bin/bash
# Pass as --user-data-file when launching the Oracle instance. Adds an alternate SSH port
# (2222) for networks that block 22, and opens it in the image's stock iptables rules.
sed -i 's/^#Port 22/Port 22/' /etc/ssh/sshd_config
grep -qxF 'Port 2222' /etc/ssh/sshd_config || echo 'Port 2222' >> /etc/ssh/sshd_config
iptables -I INPUT -p tcp --dport 2222 -j ACCEPT
RULES=/etc/iptables/rules.v4
if [ -f "$RULES" ] && ! grep -q -- '--dport 2222' "$RULES"; then
  sed -i '0,/-A INPUT -j REJECT/s//-A INPUT -p tcp -m state --state NEW -m tcp --dport 2222 -j ACCEPT\n&/' "$RULES"
fi
systemctl restart ssh
