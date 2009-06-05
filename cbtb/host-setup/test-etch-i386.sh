#!/bin/sh -x

# Run the etch/i386 image using -snapshot to verify that it works.
# The template should be left unmodified.

# $Id$
# Copyright 2007 Google Inc.
# Author: Drake Diedrich <dld@google.com>
# License: GPLv2

set -e

if [ "x$MACFILE" = "x" -o "x$MACADDR" = "x" -o "x$IFACE" = "x" \
     -o "x$IPADDR" = "x" ] ; then
  echo "Run this script under tunbr"
  exit 1
fi

# defaults, overridden by /etc/default/testenv if it exists
# diskimgdir should be local for reasonable performance
size=2G
diskimgdir=${HOME}/.testenv
tftpdir=/tftpboot
qemu_i386=qemu  # could be kvm, kqemu version, etc.  Must be 0.9.0 to net boot.

[ -x /etc/default/testenv ] && . /etc/default/testenv



IMAGE=etch-i386
IMAGEDIR=${diskimgdir}/${IMAGE}
diskimg=${IMAGEDIR}/hda.img

tmpdir=`mktemp -d /tmp/${IMAGE}.XXXXXX`
SERIAL=${tmpdir}/serial
MONITOR=${tmpdir}/monitor
VNC=${tmpdir}/vnc

if [ ! -f ${diskimg} ] ; then

  echo "No template image ${diskimg} exists yet."
  echo "Run tunbr etch-i386.sh first."
  exit 1
fi

echo IPADDR=${IPADDR}  tmpdir=${tmpdir}

${qemu_i386} -snapshot \
  -serial unix:${SERIAL},server,nowait \
  -monitor unix:${MONITOR},server,nowait \
  -vnc unix:${VNC} \
  -net nic,macaddr=${MACADDR} \
  -net tap,ifname=${IFACE},script=no \
  -boot c -hda ${diskimg} -no-reboot & qemu=$!

# kill the emulator if any abort-like signal is received
trap "kill -9 ${qemu} ; exit 1" 1 2 3 6 14 15

while ! ping -c 1 -w 10 ${IPADDR} 2>/dev/null
do
  echo -n .
done
echo " ping succeeded"

while ! ssh -o StrictHostKeyChecking=no root@${IPADDR} hostname
do
  echo -n .
  sleep 10
done

date

# execute any parameters here
if [ "x${execfiles}" != "x" ]
then
  scp ${execfiles} root@${IPADDR}: </dev/null || true
  for f in ${execfiles}
  do
    ssh root@${IPADDR} ./${f} || true
  done
fi


ssh root@${IPADDR} halt

wait

echo "Instance shut down, removing ssh hostkey"
sed -i /^${IPADDR}\ .*\$/d ~/.ssh/known_hosts

