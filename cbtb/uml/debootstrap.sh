#!/bin/bash -x

#
# Make a tarball of the root system of a basic Ubunutu/dapper system,
# for use in preparing UML root partition images
#

# $Id$
# Copyright 2007 Google Inc.
# Author: Drake Diedrich <dld@google.com>
# License: GPLv2

set -e

OLDPWD=$PWD
cd ../..
  SRC=$PWD
  BUILD_DIR="$SRC/build"
  SVNREV=`awk '/^[0-9]+$/ { print $1; }' REVISION || svnversion | tr [A-Z] [a-z] || svn info zumastor | grep ^Revision:  | cut -d\  -f2`
cd $OLDPWD

if [ "x$ARCH" = "x" ]
then
  echo "This script requires an ARCH env variable"
  exit 1
fi

if [ "x$DIST" = "x" ]
then
  echo "This script requires a DIST env variable"
  exit 1
fi

if [ "x$LINUXDISTRIBUTION" = "x" ]
then
  echo "This script requires a LINUXDISTRIBUTION env variable"
  exit 1
fi

DEBOOTSTRAP=/usr/sbin/debootstrap
SUDO=sudo

# the testenv setup, see cbtb/host-setup/
VIRTHOST=192.168.23.1
[ -x /etc/default/testenv ] && . /etc/default/testenv

rootdir=`mktemp -d`
stagefile=`mktemp`

TESTDEPENDENCIES=openssh-server,cron,postfix,dmsetup
BUILDDEPEDENCIES=build-essential,lvm2,fakeroot,kernel-package,devscripts,subversion,debhelper,libpopt-dev,zlib1g-dev,debhelper,bzip2
EXCLUDE=alsa-base,alsa-utils,eject,console-data,libasound2,linux-sound-base,memtest86,mii-diag,module-init-tools,wireless-tools,wpasupplicant,pcmciautils

# Basic dapper software installed into $rootdir
#  --exclude=$EXCLUDE
url=http://zumastor.googlecode.com/files/$DIST-$ARCH.tar.gz
tries=0
if [ ! -f /tmp/$DIST-$ARCH.tgz ]
then
  while true
  do
    [ $tries -gt 5 ] && sh -c 'echo "Failed to download base tarball"; exit 1;'
    tries=$(($tries + 1))
    (wget -c $url -O /tmp/$DIST-$ARCH.tgz)
    if [ $? -eq 0 ]
    then
      break
    else
      rm -f /tmp/$DIST-$ARCH.tgz
    fi
  done
fi
$SUDO $DEBOOTSTRAP --arch $ARCH --unpack-tarball /tmp/$DIST-$ARCH.tgz \
  --include=$TESTDEPENDENCIES,$BUILDDEPEDENCIES \
  $DIST $rootdir http://$VIRTHOST/$LINUXDISTRIBUTION

# create and authorize a local ssh key for root
$SUDO mkdir -p $rootdir/root/.ssh
$SUDO ssh-keygen -q -P '' -N '' -t dsa -f $rootdir/root/.ssh/id_dsa
$SUDO cat $rootdir/root/.ssh/id_dsa.pub >$stagefile

# Authorize the user to ssh into this virtual instance
if [ "x`cat ~/.ssh/*.pub`" = "x" ]
then
  echo "No ssh public key for your user found. Create one and try again"
  exit 1
fi
cat ~/.ssh/*.pub >>$stagefile
$SUDO mv $stagefile $rootdir/root/.ssh/authorized_keys
$SUDO chown root:root $rootdir/root/.ssh/authorized_keys
$SUDO chmod 600 $rootdir/root/.ssh/authorized_keys


echo unassigned >$stagefile
$SUDO mv $stagefile $rootdir/etc/hostname


cat >$stagefile <<EOF
# Used by ifup(8) and ifdown(8). See the interfaces(5) manpage or
# /usr/share/doc/ifupdown/examples for more information.

# The loopback network interface
auto lo
iface lo inet loopback

# The primary network interface
auto eth0
iface eth0 inet dhcp
EOF
$SUDO mv $stagefile $rootdir/etc/network/interfaces
$SUDO chown root:root $rootdir/etc/network/interfaces
$SUDO chmod 644 $rootdir/etc/network/interfaces

# clean up the downloaded packages to conserve space
$SUDO rm -f $rootdir/var/cache/apt/archives/*.deb

# create and mount an empty ext3 filesystem
ext3dev=`mktemp`
ext3dir=`mktemp -d`
dd if=/dev/zero bs=1M seek=1024 count=0 of=$ext3dev
$SUDO mkfs.ext3 -F $ext3dev
$SUDO mount -oloop,rw $ext3dev $ext3dir

# tar it up the new filesystem onto the new ext3 device
$SUDO tar cf - -C $rootdir . | \
  $SUDO tar xf - -C $ext3dir

# make sure the ubd* devices are in the base image
mkdir -p $ext3dir/proc
$SUDO mount -t proc proc $ext3dir/proc
$SUDO chroot $ext3dir /bin/bash <<EOF
cd /dev
ln -sf /sbin/MAKEDEV /dev/MAKEDEV
/dev/MAKEDEV ubd
EOF
$SUDO umount $ext3dir/proc


# Some logic in the installer is hosed under debootstrap
# Just make sure this exists or DHCP will fail
# $SUDO rm -rf $ext3dir/etc/network/run
# $SUDO mkdir $ext3dir/etc/network/run

$SUDO umount $ext3dir

# copy it back into the build/ directory, avoiding NFS issues and
# potential races.
$SUDO chown $USER $ext3dev
[ -d $BUILD_DIR/r$SVNREV ] || mkdir $BUILD_DIR/r$SVNREV
mv $ext3dev $BUILD_DIR/r$SVNREV/$DIST-$ARCH-r$SVNREV.ext3
ln -sf r${SVNREV}/$DIST-$ARCH-r$SVNREV.ext3 $BUILD_DIR/$DIST-$ARCH.ext3

# cleanup
$SUDO rm -rf $rootdir
$SUDO rmdir $ext3dir
