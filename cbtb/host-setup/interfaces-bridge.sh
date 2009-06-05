#!/bin/sh -x
#
# $Id$
#
# Add the br1 bridge to /etc/network/interfaces, as required by tests in
# the tunbr virtualization environment.
#

VIRTNET="192.168.23.0/24"
VIRTHOST="192.168.23.1"
VIRTBR="br1"
[ -x /etc/default/testenv ] && . /etc/default/testenv

if echo $VIRTNET | egrep "/24"
then
  NETWORK=`echo $VIRTNET | sed s%\/24%%`
  NETMASK="255.255.255.0"
else
  echo "Configure manually.  only /24 supported by $0"
  exit 2
fi

  
if egrep "iface +${VIRTBR}" /etc/network/interfaces; then
  echo "iface ${VIRTBR} already found in /etc/network/interfaces."
  echo "Modify by hand if necessary."
  exit 1
else
  aptitude install -y bridge-utils
  cat >>/etc/network/interfaces <<EOF

auto ${VIRTBR}
iface ${VIRTBR} inet static
	pre-up brctl addbr \$IFACE
	address ${VIRTHOST}
	network ${NETWORK}
	netmask ${NETMASK}
EOF
  ifup $VIRTBR
fi
