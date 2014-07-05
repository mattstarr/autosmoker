autosmoker
==========
Code for Rasp Pi automated meat smoker and related components. Project details, diagrams and photographs located at: http://www.mattstarr.net/autosmoker.html

Notes:
----------------------------
Servo position / pulse width
90 deg L = 600 usec
45 deg L = 1050 usec
0 deg = 1500 usec
45 deg R = 1950 usec
90 deg R = 2400 usec 
from 0 to 180
usec = 600 + (10 * deg)

The following was added to /etc/init/autosmoker.conf: (after installing upstart)
description "startup smoker and web UI on start"
author "Matt Starr - matt@mattstarr.net"
start on runlevel [2345]
stop on runlevel [016]
chdir /home/pi/scripts/
exec python /home/pi/scripts/webui.py
respawn
