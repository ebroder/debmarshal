#!/bin/sh
#
# $Id$
#
# Launch the zumastor continuous build script as the zbuild user
# on bootup.  Should be installed as /etc/init.d/zbuild and
# symlinked from /etc/rc2.d/S95zbuild

case "$1" in
    start)
        rm -f /var/lib/misc/dnsmasq.leases /var/lib/misc/dnsmasq.leases.new \
           /var/lib/misc/tunbr.leases /var/lib/misc/tunbr.leases.new
        mkdir /var/run/zbuild
        chown zbuild:zbuild /var/run/zbuild
        cd ~zbuild
        su - zbuild /home/zbuild/zbuild.start
        ;;

    stop)
        rmdir /var/run/zbuild
        ;;
esac

exit 0
