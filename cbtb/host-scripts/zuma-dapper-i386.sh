#!/bin/sh -x
#
# Build an image with current or provided zumastor debs installed, booted,
# and ready to immediately run single-node tests.
# Inherits from the generic dapper template.
#
# $Id$
# Copyright 2007 Google Inc.
# Author: Drake Diedrich <dld@google.com>
# License: GPLv2

set -e

# wait for ssh to work. Parameter 1 is the number of iterations to
# attempt, parameter 2 is the account@host to try to log in to
wait_for_ssh() {
  local max=$1
  local account=$2
  local count=0
  while [ $count -lt $max ] && ! ${SSH} $account hostname 2>/dev/null
  do
    count=$(($count + 1))
    sleep 10
  done
  ${SSH} $account hostname 2>/dev/null
  return $?
}


KERNEL_VERSION=`awk '/^2\.6\.[0-9]+(\.[0-9]+)?$/ { print $1; }' ../KernelVersion`
if [ "x$KERNEL_VERSION" = "x" ] ; then
  echo "Suspect KernelVersion file"
  exit 1
fi
VERSION=`awk '/[0-9]+\.[0-9]+(\.[0-9]+)?$/ { print $1; }' ../Version`
if [ "x$VERSION" = "x" ] ; then
  echo "Suspect Version file"
  exit 1
fi
if [ "x$SVNREV" = "x" ] ; then
  pushd ..
  SVNREV=`awk '/^[0-9]+$/ { print $1; }' SVNREV || svnversion | tr [A-Z] [a-z] || svn info zumastor | grep ^Revision:  | cut -d\  -f2`
  popd
fi
ARCH=i386

SSH='ssh -o StrictHostKeyChecking=no'
SCP='timeout -14 1800 scp -o StrictHostKeyChecking=no'
# CMDTIMEOUT='time timeout -14 120'
# KINSTTIMEOUT='time timeout -14 1200'
# SHUTDOWNTIMEOUT='time timeout -14 300'
CMDTIMEOUT=''
KINSTTIMEOUT=''
SHUTDOWNTIMEOUT=''

retval=0

if [ "x$MACFILE" = "x" -o "x$MACADDR" = "x" -o "x$IFACE" = "x" \
     -o "x$IPADDR" = "x" ] ; then
  echo "Run this script under tunbr"
  exit 1
fi

# defaults, overridden by /etc/default/testenv if it exists
# diskimgdir should be local for reasonable performance
diskimgdir=${HOME}/testenv
tftpdir=/tftpboot
qemu_img=qemu-img  # could be kvm, kqemu version, etc.
qemu_i386=qemu  # could be kvm, kqemu version, etc.
rqemu_i386=qemu  # could be kvm, kqemu version, etc.  Must be 0.9.0 to net boot
VIRTHOST=192.168.23.1
[ -x /etc/default/testenv ] && . /etc/default/testenv

IMAGE=zuma-dapper-i386
IMAGEDIR=${diskimgdir}/${IMAGE}

if [ "x$DISKIMG" = "x" ] ; then
  DISKIMG=./hda.img
fi
  
SERIAL=${IMAGEDIR}/serial
MONITOR=${IMAGEDIR}/monitor
VNC=${IMAGEDIR}/vnc

[ -e ${IMAGEDIR} ] || mkdir -p ${IMAGEDIR}
[ -e ${IMAGEDIR}/r${SVNREV} ] || mkdir -p ${IMAGEDIR}/r${SVNREV}

if [ "x$TEMPLATEIMG" = "x" ] ; then

  TEMPLATEIMG=./dapper-i386.img

  # dereference, so multiple templates may coexist simultaneously
  if [ -L "${TEMPLATEIMG}" ] ; then
    TEMPLATEIMG=`readlink ${TEMPLATEIMG}`
  fi

  if [ ! -f "${TEMPLATEIMG}" ] ; then
    echo "No template image ${TEMPLATEIMG} exists yet."
    echo "Run tunbr dapper-i386.sh first."
    exit 1
  fi
fi

if [ -f "${DISKIMG}" ] ; then
  echo Zuma/dapper image already existed, renaming
  savelog -l -c 2 "${DISKIMG}"
fi

templatedir=`dirname "${TEMPLATEIMG}"`
diskimgdir=`dirname "${DISKIMG}"`
if [ "x$templatedir" = "x$diskimgdir" ] ; then
  pushd $templatedir
  ${qemu_img} create  -b `basename "${TEMPLATEIMG}"` -f qcow2 `basename "${DISKIMG}"`
  popd
else
  ln -sf ../${TEMPLATEIMG} $diskimgdir/dapper-i386.img
  pushd $diskimgdir
    ${qemu_img} create  -b dapper-i386.img -f qcow2 "${DISKIMG}"
  popd
fi

${rqemu_i386} -m 512 \
  -serial unix:${SERIAL},server,nowait \
  -monitor unix:${MONITOR},server,nowait \
  -vnc unix:${VNC} \
  -net nic,macaddr=${MACADDR} \
  -net tap,ifname=${IFACE},script=no \
  -boot c -hda "${DISKIMG}" -no-reboot & qemu_pid=$!
  

if ! wait_for_ssh 30 root@${IPADDR}
then
  if [ "x$LOGDIR" != "x" ] ; then
    socat - unix:${MONITOR} <<EOF
      screendump $LOGDIR/install.ppm
EOF
    convert $LOGDIR/install.ppm $LOGDIR/install.png
    rm $LOGDIR/install.ppm
  fi
  kill -9 $qemu_pid
  retval=64
  unset qemu_pid
fi

date

# strip the root password off the specific test image.
# Makes it portable to anyone.
${SSH} root@${IPADDR} 'sed -i s/^root:x:/root::/ /etc/passwd'

# blacklist ide_generic for qemu/dapper's benefit
${CMDTIMEOUT} ${SSH} root@${IPADDR} 'echo blacklist ide_generic >>/etc/modprobe.d/blacklist' 

# create a tmpfs /tmp on the instance to place the debs into
${SSH} root@${IPADDR} 'mount -t tmpfs tmpfs /tmp'

# copy the debs that were built in the build directory
# onto the new zuma template instance
for f in \
    ddsnap_build_${ARCH}.deb \
    zumastor_build_all.deb \
    kernel-headers-build_${ARCH}.deb \
    kernel-image-build_${ARCH}.deb
do
  ${SCP} $f root@${IPADDR}:/tmp || retval=$?
done

# install the copied debs in the correct order
${CMDTIMEOUT} ${SSH} root@${IPADDR} aptitude install -y tree || retval=$?
${KINSTTIMEOUT} ${SSH} root@${IPADDR} dpkg -i /tmp/kernel-image-build_${ARCH}.deb || retval=$?
${CMDTIMEOUT} ${SSH} root@${IPADDR} dpkg -i /tmp/ddsnap_build_${ARCH}.deb || retval=$?
${CMDTIMEOUT} ${SSH} root@${IPADDR} dpkg -i /tmp/zumastor_build_all.deb || retval=$?
${CMDTIMEOUT} ${SSH} root@${IPADDR} 'rm /tmp/*.deb' || retval=$?
${CMDTIMEOUT} ${SSH} root@${IPADDR} apt-get clean || retval=$?

# temporary hack before going to LABEL= or UUID=
${CMDTIMEOUT} ${SSH} root@${IPADDR} 'sed -i s/hda/sda/ /boot/grub/menu.lst' || retval=$?
${CMDTIMEOUT} ${SSH} root@${IPADDR} 'sed -i s/hda/sda/ /etc/fstab' || retval=$?

# qemu still doesn't do apic's well with linux.  Take it off the menu.
${CMDTIMEOUT} ${SSH} root@${IPADDR} "sed --in-place 's/^#\ kopt=root=/#\ kopt=noapic\ root=/' /boot/grub/menu.lst " || retval=$?

# update grub
${CMDTIMEOUT} ${SSH} root@${IPADDR} 'update-grub' || retval=$?

# halt the new image, and wait for qemu to exit
${CMDTIMEOUT} ${SSH} root@${IPADDR} poweroff

time wait $qemu_pid || retval=$?
kill -0 $qemu_pid && kill -9 $qemu_pid

exit $retval
