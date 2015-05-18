autosmoker
==========
Code for Rasp Pi automated meat smoker and related components. Project details, diagrams and photographs located at: http://www.mattstarr.net/index.php/auto-smoker

Notes:
----------------------------
Servo position / pulse width<br>
90 deg L = 600 usec<br>
45 deg L = 1050 usec<br>
0 deg = 1500 usec<br>
45 deg R = 1950 usec<br>
90 deg R = 2400 usec<br>
from 0 to 180<br>
usec = 600 + (10 * deg)<br>

The following was added to /etc/init/autosmoker.conf: (after installing upstart)<br>
description "startup smoker and web UI on start"<br>
author "Matt Starr - matt@mattstarr.net"<br>
start on runlevel [2345]<br>
stop on runlevel [016]<br>
chdir /home/pi/scripts/<br>
exec python /home/pi/scripts/smokehandler.py<br>
exec python /home/pi/scripts/servoreader.py<br>
respawn<br>

