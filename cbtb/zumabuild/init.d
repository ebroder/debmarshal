#!/bin/sh
#
# $Id$
#
# Launch the zumastor continuous build script as the zuabuild user
# on bootup.  Should be installed as /etc/init.d/zuabuild and
# symlinked from /etc/rc2.d/S95zuabuild

case "$1" in
    start)
        rm -f /var/lib/misc/dnsmasq.leases /var/lib/misc/dnsmasq.leases.new \
           /var/lib/misc/tunbr.dnsmasq /var/lib/misc/tunbr.dnsmasq.new
        mkdir /var/run/zuabuild || true
        chown zuabuild:zuabuild /var/run/zuabuild
        cd ~zuabuild
        su - zuabuild /home/zuabuild/zuabuild.start
        ;;

    stop)
        rmdir /var/run/zuabuild
        ;;
esac

exit 0
