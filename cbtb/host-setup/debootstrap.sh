#!/bin/sh
#
# $Id: proxy.sh 1198 2007-12-22 11:43:15Z drake.diedrich $
#
# Install debootstrap and configure for dapper if necessary

set -e

VIRTNET="192.168.23.0/24"
VIRTHOST="192.168.23.1"
[ -x /etc/default/testenv ] && . /etc/default/testenv

# install debootstrap
if [ ! -x /usr/sbin/debootstrap ]
then
  if [ -f /etc/debian_version ]
  then
    sudo apt-get update
    sudo aptitude install -y debootstrap
  fi
fi

# and add dapper configuration if necessary
# Debian's deboostrap doesn't support dapper's default_mirror function
debootstrapdir=
[ -d /usr/lib/debootstrap ] && debootstrapdir=/usr/lib/debootstrap
[ -d /usr/share/debootstrap ] && debootstrapdir=/usr/share/debootstrap
if [ ! -f $debootstrapdir/scripts/dapper ]
then
  tmpdir=`mktemp -d`
  pushd $tmpdir
  wget http://archive.ubuntu.com/ubuntu/pool/main/d/debootstrap/debootstrap_1.0.7.tar.gz
  tar zxvf debootstrap_1.0.7.tar.gz debootstrap/scripts/ubuntu/dapper
  sed -i 's/default_mirror/# default_mirror/' debootstrap/scripts/ubuntu/dapper
  sudo mv debootstrap/scripts/ubuntu/dapper $debootstrapdir/scripts/dapper
  popd
  rm -rf $tmpdir
fi

