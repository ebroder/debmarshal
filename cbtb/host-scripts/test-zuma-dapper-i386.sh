#!/bin/sh -x

# Run the zuma/dapper/i386 image using -snapshot to verify that it works.
# The template should be left unmodified.
# Any parameters are copied to the destination instance and executed as root

# $Id$
# Copyright 2007 Google Inc.
# Author: Drake Diedrich <dld@google.com>
# License: GPLv2

set -e

# wait for file.  The first argument is the timeout, the second the file.
timeout_file_wait() {
  local max=$1
  local file=$2
  local count=0
  while [ ! -e $file ] && [ $count -lt $max ]
  do
    count=$(($count + 1))
    sleep 1
  done
  [ -e $file ]
  return $?
}

SSH='ssh -o StrictHostKeyChecking=no'
SCP='scp -o StrictHostKeyChecking=no'
# CMDTIMEOUT='timeout -14 120'
CMDTIMEOUT=''

retval=0

execfiles="$*"

if [ "x$MACFILE" = "x" -o "x$MACADDR" = "x" -o "x$IFACE" = "x" \
     -o "x$IPADDR" = "x" ] ; then
  echo "Run this script under at least one tunbr"
  exit 1
fi

# defaults, overridden by /etc/default/testenv if it exists
# diskimgdir should be local for reasonable performance
diskimgdir=${HOME}/testenv
tftpdir=/tftpboot
qemu_i386=qemu  # could be kvm, kqemu version, etc.  Must be 0.9.0 to net boot.
rqemu_i386=qemu # could be kvm, kqemu version, etc.  Must be 0.9.0 to net boot.

VIRTHOST=192.168.23.1
[ -x /etc/default/testenv ] && . /etc/default/testenv

IMAGE=zuma-dapper-i386
IMAGEDIR=${diskimgdir}/${IMAGE}
BUILDSRC=${top}/zumastor/build
if [ "x$DISKIMG" = "x" ] ; then
  diskimg=${IMAGEDIR}/hda.img
else
  diskimg="$DISKIMG"
fi

tmpdir=`mktemp -d /tmp/${IMAGE}.XXXXXX`
MONITOR=${tmpdir}/monitor
VNC=${tmpdir}/vnc
if [ "x$LOGDIR" != "x" ] ; then
  SERIAL=${LOGDIR}/${LOGPREFIX}serial
  SERIAL2=${LOGDIR}/${LOGPREFIX}serial2
  SERIAL3=${LOGDIR}/${LOGPREFIX}serial3
else
  SERIAL=${tmpdir}/serial
  SERIAL2=${tmpdir}/serial2
  SERIAL3=${tmpdir}/serial3
fi


if [ ! -f ${diskimg} ] ; then

  echo "No template image ${diskimg} exists yet."
  echo "Run tunbr zuma-dapper-i386.sh first."
  exit 1
fi

env
echo control/tmp dir=${tmpdir}


# scrape HD[BCD]SIZE from the test script, create,
# and store qemu parameters in $qemu_hd and $qemu2_hd in the $tmpdir.
largest_hdbsize=0
largest_hdcsize=0
largest_hddsize=0
for f in ${execfiles}
do
  hdbsize=`awk -F = '/^HDBSIZE=[0-9]+$/ { print $2; }' ./${f} | tail -1`
  if [ "x$hdbsize" = "x" ]
  then
    hdbsize=`awk -F = '/^DEV1SIZE=[0-9]+$/ { print $2; }' ./${f} | tail -1`
  fi
  if [ "x$hdbsize" != "x" ] ; then
    if [ "$hdbsize" -ge "$largest_hdbsize" ] ; then
      largest_hdbsize=$hdbsize
    fi
  fi
  hdcsize=`awk -F = '/^HDCSIZE=[0-9]+$/ { print $2; }' ./${f} | tail -1`
  if [ "x$hdcsize" = "x" ]
  then
    hdcsize=`awk -F = '/^DEV2SIZE=[0-9]+$/ { print $2; }' ./${f} | tail -1`
  fi
  if [ "x$hdcsize" != "x" ] ; then
    if [ "$hdcsize" -ge "$largest_hdcsize" ] ; then
      largest_hdcsize=$hdcsize
    fi
  fi
  hddsize=`awk -F = '/^HDDSIZE=[0-9]+$/ { print $2; }' ./${f} | tail -1`
  if [ "x$hddsize" = "x" ]
  then
    hddsize=`awk -F = '/^DEV3SIZE=[0-9]+$/ { print $2; }' ./${f} | tail -1`
  fi
  if [ "x$hddsize" != "x" ] ; then
    if [ "$hddsize" -ge "$largest_hddsize" ] ; then
      largest_hddsize=$hddsize
    fi
  fi
done
qemu_hd=""
qemu2_hd=""
qemu3_hd=""
if [ $largest_hdbsize -gt 0 ] ; then
  qemu-img create ${tmpdir}/hdb.img ${largest_hdbsize}M
  qemu_hd="-hdb ${tmpdir}/hdb.img"
  if [ "x$MACADDR2" != "x" ] ; then
    qemu-img create ${tmpdir}/hdb2.img ${largest_hdbsize}M
    qemu2_hd="-hdb ${tmpdir}/hdb2.img"
  fi
  if [ "x$MACADDR3" != "x" ] ; then
    qemu-img create ${tmpdir}/hdb3.img ${largest_hdbsize}M
    qemu3_hd="-hdb ${tmpdir}/hdb3.img"
  fi
fi
if [ $largest_hdcsize -gt 0 ] ; then
  qemu-img create ${tmpdir}/hdc.img ${largest_hdcsize}M
  qemu_hd="${qemu_hd} -hdc ${tmpdir}/hdc.img"
  if [ "x$MACADDR2" != "x" ] ; then
    qemu-img create ${tmpdir}/hdc2.img ${largest_hdcsize}M
    qemu2_hd="${qemu2_hd} -hdc ${tmpdir}/hdc2.img"
  fi
  if [ "x$MACADDR3" != "x" ] ; then
    qemu-img create ${tmpdir}/hdc3.img ${largest_hdcsize}M
    qemu3_hd="${qemu3_hd} -hdc ${tmpdir}/hdc3.img"
  fi
fi
if [ $largest_hddsize -gt 0 ] ; then
  qemu-img create ${tmpdir}/hdd.img ${largest_hddsize}M
  qemu_hd="${qemu_hd} -hdd ${tmpdir}/hdd.img"
  if [ "x$MACADDR2" != "x" ] ; then
    qemu-img create ${tmpdir}/hdd2.img ${largest_hddsize}M
    qemu2_hd="${qemu2_hd} -hdd ${tmpdir}/hdd2.img"
  fi
  if [ "x$MACADDR3" != "x" ] ; then
    qemu-img create ${tmpdir}/hdd3.img ${largest_hddsize}M
    qemu3_hd="${qemu3_hd} -hdd ${tmpdir}/hdd3.img"
  fi
fi

# TODO(dld): add back  -loadvm running  when method to deal with changed
# ethernet/IP allocations is developed.
${rqemu_i386} -m 512 \
  -serial file:${SERIAL} \
  -monitor unix:${MONITOR},server,nowait \
  -vnc unix:${VNC} \
  -net nic,macaddr=${MACADDR},model=ne2k_pci \
  -net tap,ifname=${IFACE},script=no \
  -snapshot -hda ${diskimg} ${qemu_hd} \
  -boot c -no-reboot & qemu_pid=$!
if ! timeout_file_wait 30 ${MONITOR}
then
  echo First qemu instance never started, test harness problem.  Aborting.
  kill -0 $qemu_pid && kill -9 $qemu_pid
  exit 2
fi


socat - unix:${MONITOR} <<EOF
  info network
  info snapshots
EOF

if [ "x$MACADDR2" != "x" ] ; then
  MONITOR2=${tmpdir}/monitor2
  VNC2=${tmpdir}/vnc2
  # TODO(dld): See above.  -loadvm running
  ${rqemu_i386} -m 512 \
    -serial file:${SERIAL2} \
    -monitor unix:${MONITOR2},server,nowait \
    -vnc unix:${VNC2} \
    -net nic,macaddr=${MACADDR2},model=ne2k_pci \
    -net tap,ifname=${IFACE2},script=no \
    -snapshot -hda ${diskimg} ${qemu2_hd} \
    -boot c -no-reboot & qemu2_pid=$!
  if ! timeout_file_wait 30 ${MONITOR2}
  then
    echo Second qemu instance never started, test harness problem.  Aborting.
    kill -0 $qemu_pid && kill -9 $qemu_pid
    kill -0 $qemu2_pid && kill -9 $qemu2_pid
    exit 2
  fi
fi

if [ "x$MACADDR3" != "x" ] ; then
  MONITOR3=${tmpdir}/monitor3
  VNC3=${tmpdir}/vnc3
  # TODO(dld): See above.  -loadvm running
  ${rqemu_i386} -m 512 \
    -serial file:${SERIAL3} \
    -monitor unix:${MONITOR3},server,nowait \
    -vnc unix:${VNC3} \
    -net nic,macaddr=${MACADDR3},model=ne2k_pci \
    -net tap,ifname=${IFACE3},script=no \
    -snapshot -hda ${diskimg} ${qemu3_hd} \
    -boot c -no-reboot & qemu3_pid=$!
  if ! timeout_file_wait 30 ${MONITOR3}
  then
    echo Third qemu instance never started, test harness problem.  Aborting.
    kill -0 $qemu_pid && kill -9 $qemu_pid
    kill -0 $qemu2_pid && kill -9 $qemu2_pid
    kill -0 $qemu3_pid && kill -9 $qemu3_pid
    exit 2
  fi
fi


# kill the emulator if any abort-like signal is received
trap "kill -9 ${qemu_pid} ${qemu2_pid} ${qemu3_pid} ; exit 1" 1 2 3 6 14 15

count=0
while [ $count -lt 30 ] && ! ${SSH} root@${IPADDR} hostname 2>/dev/null
do
  count=$(( count + 1 ))
  echo -n .
  sleep 10
done
if [ $count -ge 30 ]
then
  if [ "x$LOGDIR" != "x" ] ; then
    socat - unix:${MONITOR} <<EOF
screendump $LOGDIR/${LOGPREFIX}screen.ppm
EOF
    convert $LOGDIR/${LOGPREFIX}screen.ppm $LOGDIR/${LOGPREFIX}screen.png
    rm $LOGDIR/${LOGPREFIX}screen.ppm
  fi
  kill -9 $qemu_pid
  retval=64
  unset qemu_pid
fi

if [ "x$MACADDR2" != "x" ] ; then
  count=0
  while [ $count -lt 30 ] && ! ${SSH} root@${IPADDR2} hostname 2>/dev/null
  do
    count=$(( count + 1 ))
    echo -n .
    sleep 10
  done

  if [ $count -ge 30 ]
  then
    if [ "x$LOGDIR" != "x" ] ; then
      socat - unix:${MONITOR2} <<EOF
screendump $LOGDIR/${LOGPREFIX}screen2.ppm
EOF
      convert $LOGDIR/${LOGPREFIX}screen2.ppm $LOGDIR/${LOGPREFIX}screen2.png
      rm $LOGDIR/${LOGPREFIX}screen2.ppm
    fi
    kill -9 $qemu2_pid
    retval=65
    unset qemu2_pid
  fi
fi

if [ "x$MACADDR3" != "x" ] ; then
  count=0
  while [ $count -lt 30 ] && ! ${SSH} root@${IPADDR3} hostname 2>/dev/null
  do
    count=$(( count + 1 ))
    echo -n .
    sleep 10
  done

  if [ $count -ge 30 ]
  then
    if [ "x$LOGDIR" != "x" ] ; then
      socat - unix:${MONITOR3} <<EOF
screendump $LOGDIR/${LOGPREFIX}screen3.ppm
EOF
      convert $LOGDIR/${LOGPREFIX}screen3.ppm $LOGDIR/${LOGPREFIX}screen3.png
      rm $LOGDIR/${LOGPREFIX}screen3.ppm
    fi
    kill -9 $qemu3_pid
    retval=66
    unset qemu3_pid
  fi
fi

params="IPADDR=${IPADDR}"
if [ "x$IPADDR2" != "x" ] ; then
  params="${params} IPADDR2=${IPADDR2}"
fi
if [ "x$IPADDR3" != "x" ] ; then
  params="${params} IPADDR3=${IPADDR3}"
fi

# Supply device names as environment variables
if [ "x${DEV1NAME}" != "x" ]
then
  params="${params} DEV1NAME=${DEV1NAME}"
fi
if [ "x${DEV2NAME}" != "x" ]
then
  params="${params} DEV2NAME=${DEV2NAME}"
fi
if [ "x${DEV3NAME}" != "x" ]
then
  params="${params} DEV3NAME=${DEV3NAME}"
fi

# execute any parameters here, but only if all instances booted
if [ "x${execfiles}" != "x" ] && [ $retval -eq 0 ]
then
  ${CMDTIMEOUT} ${SCP} ${execfiles} root@${IPADDR}: </dev/null || true
  for f in ${execfiles}
  do
    # scrape TIMEOUT from the test script and store in the $timeout variable
    timelimit=`awk -F = '/^TIMEOUT=[0-9]+$/ { print $2; }' ./${f} | tail -1`
    if [ "x$timelimit" = "x" ] ; then
      timeout=""
    else
      timeout="timeout -14 $timelimit"
    fi

    if ${timeout} ${SSH} root@${IPADDR} ${params} ./${f}
    then
      echo ${f} ok
    else
      retval=$?
      echo ${f} not ok
    fi
  done
fi


# Kill emulators if more than 10 minutes pass during shutdown
# They haven't been dying properly
if [ "x$qemu_pid" != "x" ] ; then
  ( sleep 600 ; kill -9 $qemu_pid ) & killer=$!
fi
if [ "x$qemu2_pid" != "x" ] ; then
  ( sleep 600 ; kill -9 $qemu2_pid ) & killer2=$!
fi
if [ "x$qemu3_pid" != "x" ] ; then
  ( sleep 600 ; kill -9 $qemu3_pid ) & killer3=$!
fi

if [ "x$qemu_pid" != "x" ] ; then
  ${CMDTIMEOUT} ${SSH} root@${IPADDR} poweroff
fi

if [ "x$qemu2_pid" != "x" ] ; then
  ${CMDTIMEOUT} ${SSH} root@${IPADDR2} poweroff
fi

if [ "x$qemu3_pid" != "x" ] ; then
  ${CMDTIMEOUT} ${SSH} root@${IPADDR3} poweroff
fi

sed -i /^${IPADDR}\ .*\$/d ~/.ssh/known_hosts || true
if [ "x$IPADDR2" != "x" ] ; then
  sed -i /^${IPADDR2}\ .*\$/d ~/.ssh/known_hosts || true
fi
if [ "x$IPADDR3" != "x" ] ; then
  sed -i /^${IPADDR3}\ .*\$/d ~/.ssh/known_hosts || true
fi

if [ "x$qemu_pid" != "x" ] ; then
  time wait ${qemu_pid} || retval=$?
  kill -0 ${qemu_pid} && kill -9 ${qemu_pid}
fi

if [ "x$qemu2_pid" != "x" ] ; then
  time wait ${qemu2_pid} || retval=$?
  kill -0 ${qemu2_pid} && kill -9 ${qemu2_pid}
fi

if [ "x$qemu3_pid" != "x" ] ; then
  time wait ${qemu3_pid} || retval=$?
  kill -0 ${qemu3_pid} && kill -9 ${qemu3_pid}
fi


# clean up the 10 minute shutdown killers
if [ "x$killer" != "x" ] ; then
  kill -0 $killer && kill -9 $killer
fi
if [ "x$killer2" != "x" ] ; then
  kill -0 $killer2 && kill -9 $killer2
fi
if [ "x$killer3" != "x" ] ; then
  kill -0 $killer3 && kill -9 $killer3
fi

rm -rf ${tmpdir}

exit ${retval}
