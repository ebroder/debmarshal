#!/bin/sh
#
# $Id$
#
# Install and configure atftpd for use with the virtualization test
# environment for zumastor.
#
# Copyright 2007 Google Inc.  All rights reserved.
# Author: Drake Diedrich (dld@google.com)

VIRTHOST="192.168.23.1"
[ -x /etc/default/testenv ] && . /etc/default/testenv

# Create /tftpboot if it doesn't exist.  May already be a symlink or
# directory.
[ -e /tftpboot ] || mkdir /tftpboot

# tunbr is happier when this directory exists, and atftpd serves it.
[ -e /tftpboot/pxelinux.0 ] || mkdir /tftpboot/pxelinux.0

# Some scripts users run may also need a subdirectory of /tftpboot
# owned by the unprivileged user.  Check if running under sudo and
# create a directory for that user.
if test -n "$SUDO_USER"; then
  mkdir -m 755 /tftpboot/${SUDO_USER}
  chown ${SUDO_USER} /tftpboot/${SUDO_USER}
else
  echo "Some scripts may require dedicated per-user subdirectories in /tftpboot."
  echo "   sudo mkdir -m 755 /tftpboot/UID"
  echo "   sudo chown UID /tftpboot/UID"
fi

# preferred over apt-get, remembers what was a dependency and what was
# actually requested.
aptitude -y install atftpd

# This default config file is always installed by the atftpd package
. /etc/default/atftpd

# inetd doesn't know how to bind to individual interfaces or addresses,
# and some hosts use xinetd instead.  Just run atftpd standalone.
if [ "$USE_INETD" = "true" ] ; then
  sed -i s/USE_INETD=true/USE_INETD=false/ /etc/default/atftpd
fi

# Make sure the atftpd options include --daemon
if ! echo $OPTIONS | egrep daemon ; then
  sed -i s/OPTIONS=\"/OPTIONS=\"--daemon / /etc/default/atftpd
fi

# make sure atftpd only binds to the host-only IP address 192.168.23.1,
# so it's only serving to local instances, not the rest of the world.
if ! echo $OPTIONS | egrep bind-address ; then
  sed -i "s/=\"/=\"--bind-address $VIRTHOST /" /etc/default/atftpd
fi

# restart atftpd now that it's been reconfigured as a daemon
/etc/init.d/atftpd restart

# Populate /tftpboot with the Debian and Ubuntu network installers.
# Allow any user (particularly the atftpd user) to access them.
UBUNTUARCHIVE="http://archive.ubuntu.com/ubuntu"
DEBIANARCHIVE="http://ftp.us.debian.org/debian"
cd /tftpboot
wget -O - ${UBUNTUARCHIVE}/dists/dapper/main/installer-i386/current/images/netboot/netboot.tar.gz | tar zxvf -
wget -O - ${UBUNTUARCHIVE}/dists/dapper/main/installer-amd64/current/images/netboot/netboot.tar.gz | tar zxvf -
wget -O - ${DEBIANARCHIVE}/dists/etch/main/installer-amd64/current/images/netboot/netboot.tar.gz | tar zxvf -
wget -O - ${DEBIANARCHIVE}/dists/etch/main/installer-i386/current/images/netboot/netboot.tar.gz | tar zxvf -
chmod -R o+rX .
