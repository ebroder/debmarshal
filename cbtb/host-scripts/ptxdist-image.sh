#!/bin/bash -x
#
# $Id$
#
# based partially on buildcurrent.sh
# builds a ptxdist image with zumastor kernel and userland support
#
# Copyright 2007 Google Inc.
# Author: Chuan-kai Lin (cklin@google.com)

KERNEL_VERSION=`awk '/^2\.6\.[0-9]+(\.[0-9]+)?$/ { print $1; }' KernelVersion`
if [ "x$KERNEL_VERSION" = "x" ] ; then
  echo "Suspect KernelVersion file"
  exit 1
fi

VERSION=`awk '/^[0-9]+\.[0-9]+(\.[0-9]+)?$/ { print $1; }' Version`
if [ "x$VERSION" = "x" ] ; then
  echo "Suspect Version file"
  exit 1
fi

SVNREV=`awk '/^[0-9]+$/ { print $1; }' SVNREV || svnversion | tr [A-Z] [a-z] || svn info zumastor | grep ^Revision:  | cut -d\  -f2`

SRC=${PWD}
BUILD_DIR=${SRC}/build
LOG=/dev/null
TIME=`date +%s`

[ -d $BUILD_DIR ] || mkdir $BUILD_DIR
pushd $BUILD_DIR >> $LOG || exit 1

if [ ! -f zumastor_${VERSION}-r${SVNREV}_i386.deb ] ; then
    echo "You need to run either build_packages.sh or buildcurren.sh first"
    exit 1
fi

if [ ! -d ptxdist-build ] ; then
    # Set up a new system image project
    cp /usr/lib/ptxdist-1.0.0/config/setup/ptxdistrc.default .ptxdistrc
    ptxdist clone OSELAS.BSP-Pengutronix-GenericI586Glibc-3 ptxdist-build
    mv .ptxdistrc ptxdist-build
    pushd ptxdist-build >> $LOG

    # Configure build toolchain
    ptxdist toolchain /opt/OSELAS.Toolchain-1.1.0/i586-unknown-linux-gnu/gcc-4.1.2-glibc-2.5-kernel-2.6.18/bin
    # Copy configuration file and additional build rules
    cp ${SRC}/cbtb/ptxdist/ptxconfig .
    cp ${SRC}/cbtb/ptxdist/rules/* rules

    # Build
    ptxdist go

    # Save built root directory tree
    mv root root-pristine
    popd >> $LOG
fi

# Copy saved built root directory tree
cd ptxdist-build
rm -Rf root
cp -a root-pristine root

# Unpack Zumastor package files
dpkg -X ../kernel-image-${KERNEL_VERSION}-zumastor-r${SVNREV}_1.0_i386.deb root
dpkg -X ../zumastor_${VERSION}-r${SVNREV}_i386.deb root
dpkg -X ../ddsnap_${VERSION}-r${SVNREV}_i386.deb root
install -d root/var/log/zumastor
ln -s ../init.d/zumastor root/etc/rc.d/S04_zumastor

# Make grub boot from the Zumastor kernel
sed -i -r 's/^default.+/default	1/' root/boot/grub/menu.lst
sed -i -r 's/^timeout.+/timeout	1/' root/boot/grub/menu.lst
cat <<EOF >> root/boot/grub/menu.lst

title	Zumastor
root	(hd0,0)
kernel	/boot/vmlinuz-${KERNEL_VERSION}-zumastor-r${SVNREV} root=/dev/hda1 rw console=ttyS0,115200n8
EOF

# Create other files needed by Zumastor
install -D ${SRC}/cbtb/ptxdist/files/init-functions root/lib/lsb/init-functions
install -D ${SRC}/cbtb/ptxdist/files/lvm root/etc/init.d/lvm
ln -s ../init.d/lvm root/etc/rc.d/S03_lvm
ln -s mke2fs root/sbin/mkfs.ext3

# Disable ramfs mounts in fstab
sed -i '/ramfs/d' root/etc/fstab

# Mount debugfs for blktrace
echo none /sys/kernel/debug debugfs defaults 0 0 >> root/etc/fstab

# Make getty use the serial console
sed -i 's/tty1/ttyS0/' root/etc/inittab

# Configure eth0 to use DHCP
install ${SRC}/cbtb/ptxdist/files/interfaces root/etc/network/interfaces

# Set up sysvg volume and chmod /home on first boot
install ${SRC}/cbtb/ptxdist/files/1st_boot.sh root/home/1st_boot.sh
cat >> root/etc/init.d/rcS <<EOF
[ -x /home/1st_boot.sh ] && /home/1st_boot.sh
EOF

# Set up image-specific ssh user keys
pushd root/home
mkdir .ssh
cat ~/.ssh/*.pub > .ssh/authorized_keys
ssh-keygen -q -P '' -t dsa -f .ssh/id_dsa
cat .ssh/id_dsa.pub >> .ssh/authorized_keys
popd

# Build the qemu-bootable system image
ptxdist images
cp images/hd.img ../zumastor.img

popd >> $LOG
echo zumastor ptxdist image successfully built in $BUILD_DIR/zumastor.img
