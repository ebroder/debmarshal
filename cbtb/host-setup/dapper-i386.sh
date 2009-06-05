#!/bin/sh -x

# Set up the initial Ubuntu/dapper template image, for use when duplicating
# the install to multiple server/client tests.  Makes use of tunbr and
# a presetup br1, squid, and dnsmasq.  Must run from the cbtb/host-setup/
# directory to use other scripts and data.

# $Id$
# Copyright 2007 Google Inc.
# Author: Drake Diedrich <dld@google.com>
# License: GPLv2

set -e

rc=0

SSH='ssh -o StrictHostKeyChecking=no'
SCP='scp -o StrictHostKeyChecking=no'

if [ "x$MACFILE" = "x" -o "x$MACADDR" = "x" -o "x$IFACE" = "x" \
     -o "x$IPADDR" = "x" ] ; then
  echo "Run this script under tunbr"
  exit 1
fi

if [ "x$SVNREV" = "x" ] ; then
  SVNREV=`svnversion || svn info | awk '/Revision:/ { print $2; }'`
fi
      

# Remove the any existing ssh hostkey for this IPADDR since generating a
# new one
if [ -f ~/.ssh/known_hosts ] ; then
  sed -i /^${IPADDR}\ .*\$/d ~/.ssh/known_hosts
fi

# defaults, overridden by /etc/default/testenv if it exists
# diskimgdir should be local for reasonable performance
size=10G
tftpdir=/tftpboot
qemu_img=qemu-img  # could be kvm, kqemu version, etc.
qemu_i386=qemu  # could be kvm, kqemu version, etc.
rqemu_i386=qemu  # could be kvm, kqemu version, etc.  Must be 0.9.0 to net boot.
VIRTHOST=192.168.23.1
[ -x /etc/default/testenv ] && . /etc/default/testenv

# default to dapper-i386-rN.img in the current directory if DISKIMG is
# unspecified.
IMAGE=dapper-i386
IMAGEDIR='.'
if [ "x$DISKIMG" = "x" ] ; then
  diskimg=${IMAGE}-r${SVNREV}.img
else
  # eg. DISKIMG=../../build/${IMAGE-r`svnversion`.img
  if [ -e "$DISKIMG" ] ; then
    rm "$DISKIMG"
  fi
  diskimg="$DISKIMG"
fi
SERIAL=${IMAGEDIR}/dapper-i386-serial
MONITOR=${IMAGEDIR}/dapper-i386-monitor
VNC=${IMAGEDIR}/dapper-i386-vnc

if [ ! -e ${IMAGEDIR} ]; then
  mkdir -p ${IMAGEDIR}
  chmod 700 ${IMAGEDIR}
fi

if [ ! -f ${diskimg} ] ; then

  # extract and repack the initrd with the desired preseed file
  tmpdir=`mktemp -d`
  mkdir ${tmpdir}/initrd
  cp dapper.cfg ${tmpdir}/initrd/preseed.cfg
  cp common.cfg ${tmpdir}/initrd/
  cp dapper-early.sh ${tmpdir}/initrd/early.sh
  cp dapper-late.sh ${tmpdir}/initrd/late.sh
  passwd=`pwgen 8 1`
  pwhash=`echo ${passwd} | mkpasswd -s --hash=md5`
  cat >>${tmpdir}/initrd/preseed.cfg <<EOF
d-i     mirror/http/hostname    string ${VIRTHOST}
d-i     passwd/root-password-crypted    password ${pwhash}
d-i     passwd/user-password-crypted    password ${pwhash}
d-i	passwd/user-fullname            string ${USER}
d-i	passwd/username                 string ${USER}
EOF

  cat ~/.ssh/*.pub > ${tmpdir}/initrd/authorized_keys

  if [ ! -d  ${tftpdir}/${USER}/ubuntu-installer/i386 ] ; then
    mkdir -p ${tftpdir}/${USER}/ubuntu-installer/i386
  fi

  fakeroot <<EOF
cd ${tmpdir}/initrd
zcat ${tftpdir}/ubuntu-installer/i386/initrd.gz | cpio -i
find . -print0 | cpio -0 -o -H newc | gzip -9 > ${tftpdir}/${USER}/ubuntu-installer/i386/initrd.gz
EOF
  chmod ugo+r ${tftpdir}/${USER}/ubuntu-installer/i386/initrd.gz
  
  ${qemu_img} create -f qcow2 ${diskimg} ${size}

  cat >${MACFILE} <<EOF
DEFAULT server
LABEL server
	kernel ubuntu-installer/i386/linux
	append base-config/package-selection= base-config/install-language-support=false vga=normal initrd=${USER}/ubuntu-installer/i386/initrd.gz ramdisk_size=13531 root=/dev/rd/0 rw preseed/file=/preseed.cfg noapic DEBCONF_DEBUG=5
PROMPT 0
TIMEOUT 1
EOF
  chmod ugo+r ${MACFILE}

  ${rqemu_i386} \
    -serial unix:${SERIAL},server,nowait \
    -monitor unix:${MONITOR},server,nowait \
    -vnc unix:${VNC} \
    -net nic,macaddr=${MACADDR} -net tap,ifname=${IFACE},script=no \
    -boot n -hda ${diskimg} -no-reboot & qemu_pid=$!
 
  # kill the emulator if any abort-like signal is received
  trap "kill -9 ${qemu_pid} ; exit 1" 1 2 3 6 14 15

  # TODO: timeout and screencapture if first boot failed
  wait $qemu_pid



  ${rqemu_i386} \
    -serial unix:${SERIAL},server,nowait \
    -monitor unix:${MONITOR},server,nowait \
    -vnc unix:${VNC} \
    -net nic,macaddr=${MACADDR} -net tap,ifname=${IFACE},script=no \
    -boot c -hda ${diskimg} -no-reboot & qemu_pid=$!

  # kill the emulator if any abort-like signal is received
  trap "kill -9 ${qemu_pid} ; exit 1" 1 2 3 6 14 15

  count=0
  while [ $count -lt 30 ] && ! ${SSH} root@${IPADDR} hostname 2>/dev/null
  do
    count=$(( count + 1 ))
    echo -n .
    sleep 10
  done
  if [ $count -ge 30 ] ; then
    kill -9 $qemu_pid
    rc=65
    unset qemu_pid

  else
    # turn the swap partition into LVM2 sysvg
    ${SCP} swap2sysvg.sh root@${IPADDR}:
    ${SSH} root@${IPADDR} './swap2sysvg.sh && rm swap2sysvg.sh'

    # remove the root password from the template image
    ${SSH} root@${IPADDR} "sed -i 's/^root:[^:]*:/root::/' /etc/passwd"

    # generate and authorize an passwordless ssh key that can log in to
    # any other image with this as its base template
    ${SSH} root@${IPADDR} "ssh-keygen -q -P '' -t dsa -f .ssh/id_dsa ; cat .ssh/id_dsa.pub >> .ssh/authorized_keys"

    ${SSH} root@${IPADDR} halt

    wait $qemu_pid

    echo "${diskimg} installed."
    echo "mv ${diskimg} ../../build/ and symlink from dapper-i386.img if you wish to use this as a template."

  fi

  rm -rf ${tmpdir}

else
  echo "image ${diskimg} already exists."
  echo "rm if you wish to recreate it and all of its derivatives."
  rc=66
fi

exit $rc
