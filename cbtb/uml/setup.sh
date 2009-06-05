#!/bin/bash -x

# Run this only on Debian or Debian-derivative systems for now.
# Manually inspect and run the components modified as necessary on
# other systems.

set -e

stagefile=`mktemp`
tmpdir=`mktemp -d`

sudo apt-get -q --force-yes -y install devscripts build-essential fakeroot \
                                       debhelper zlib1g-dev libpopt-dev rsync \
				       uml-utilities

# install tunbr setuid root
if [ ! -x /usr/local/bin/tunbr ]
then
  OLDPWD=$PWD
  cd ../tunbr
  make tunbr
  mv tunbr $tmpdir
  sudo mv $tmpdir/tunbr /usr/local/bin
  sudo chown root /usr/local/bin/tunbr
  sudo chmod 4755 /usr/local/bin/tunbr
  cd $OLDPWD
fi

if tunctl 2>&1 | grep -q Failed
then
  sudo chmod 666 /dev/net/tun
fi

# fix this randomness
[ -d /tftpboot/pxelinux.cfg/ ] || sudo mkdir -p /tftpboot/pxelinux.cfg/

# Add br1 to /etc/network/interfaces
if ! egrep "^iface br1" /etc/network/interfaces
then
  if [ -f /etc/network/interfaces ]
  then
    cp ../host-setup/interfaces-bridge.sh $stagefile
    chmod +x $stagefile
    sudo $stagefile
  fi
fi

# Install the Apache proxy
if [ ! -f /etc/apache2/sites-available/proxy ]
then
  if [ -f /etc/debian_version ]
  then
    cp -ar ../host-setup $tmpdir
    OLDPWD=$PWD
    cd $tmpdir/host-setup
    sudo ./proxy.sh
    cd $OLDPWD
    rm -rf $tmpdir/host-setup
  fi
fi


# Install and configure dnsmasq
if [ ! -f /etc/dnsmasq.conf.distrib ]
then
  if [ -f /etc/debian_version ]
  then
    cp -ar ../host-setup $tmpdir
    OLDPWD=$PWD
    cd $tmpdir/host-setup
    sudo ./dnsmasq.sh
    cd $OLDPWD
    rm -rf $tmpdir/host-setup
  fi
fi

# Install and configure debootstrap
../host-setup/debootstrap.sh

sudo aptitude install -y libvdeplug2-dev gcc make
