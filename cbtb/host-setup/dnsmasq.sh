#!/bin/sh -x
#
# $Id$
#
#    Install and configure dnsmasq to dynamically serve DNS and DHCP
# for the range of addresses managed by tunbr, part of the zumastor
# virtual test environment.
#    The default /etc/dnsmasq.conf is locally diverted and replaced
# with the configuration file inline below, with instructions on how
# to remove the diversion if the test environment is removed or
# needs to be reinstalled.
#
# Copyright Google Inc. All rights reserved.
# Author: Drake Diedrich (dld@google.com)

VIRTNET="192.168.23.0/24"
VIRTHOST="192.168.23.1"
VIRTBR="br1"
[ -x /etc/default/testenv ] && . /etc/default/testenv

if echo $VIRTNET | egrep "/24"
then
  NETWORK=`echo $VIRTNET | sed s%\.0\/24%%`
  NETMASK="255.255.255.0"
else
  echo "Configure manually.  only /24 supported by $0"
  exit 2
fi
        

aptitude install -y dnsmasq

# only divert /etc/dnsmasq.conf once
if [ ! -f /etc/dnsmasq.conf.distrib ] ; then
  dpkg-divert --local --rename --add /etc/dnsmasq.conf

  # where tunbr will put anything it wants
  # dnsmasq to serve.  Truncate this on reboot.
  touch /var/lib/misc/tunbr.dnsmasq
fi


  cat >/etc/init.d/tunbr-dnsmasq <<EOF
#!/bin/sh

> /var/lib/misc/tunbr.dnsmasq
EOF
  chmod 755 /etc/init.d/tunbr-dnsmasq
  ln -sf /etc/init.d/tunbr-dnsmasq /etc/rcS.d/S80tunbr-dnsmasq

  # Write a new configuration file to /etc/dnsmasq.conf
  cat >/etc/dnsmasq.conf <<EOF
#
# dnsmasq configuration file for use hosting a zumastor test environment.
# dhcp-range should not use the range that tunbr is compiled to use.
# dhcp-leasefile must match the lease file that tunbr will also manage.
#
# The default configuration file for dnsmasq (/etc/dnsmasq.conf) as
# distributed by the dnsmasq package was diverted, see man dpkg-divert.
# To put things back in their original state, and to return to normal
# Debian conffile behavior, remove this diversion as follows:
#    rm /etc/dnsmasq.conf
#    dpkg-divert --remove /etc/dnsmasq.conf
#

interface=$VIRTBR
interface=lo
bind-interfaces
conf-file=/var/lib/misc/tunbr.dnsmasq
dhcp-range=$NETWORK.50,static,infinite
dhcp-leasefile=/dev/null
log-queries
dhcp-boot=/pxelinux.0,boothost,$VIRTHOST
domain-needed
bogus-priv
EOF
  /etc/init.d/dnsmasq restart

