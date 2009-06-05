#!/bin/sh -x
#
# $Id$
#
# Make use of large, extra devices on /dev/sd[bcd] to test
# multi-terabyte-sized zumastor filesystems.  RAID0 and LVM are used to
# create the large filesystems from 2045G disks provided by qemu (the
# largest supported by the 32-bit UML disk backing format).
# This is otherwise the same as the snapshot-zumastor-xfs.sh test
#
# Copyright 2007 Google Inc.  All rights reserved
# Author: Drake Diedrich (dld@google.com)


set -e

# The required sizes of the sd[bcd] devices in M.
# Read only by the test harness.
NUMDEVS=3
DEV1SIZE=2094080
DEV2SIZE=2094080
DEV3SIZE=2094080
#DEV1NAME=/dev/null
#DEV2NAME=/dev/null
#DEV3NAME=/dev/null

# Terminate test in 20 minutes.  Read by test harness.
TIMEOUT=1200

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



# additional software requirements of this test
apt-get update
aptitude install -y xfsprogs

# create LVM VG testvg
time pvcreate -ff $DEV1NAME
time pvcreate -ff $DEV2NAME
time pvcreate -ff $DEV3NAME
time vgcreate testvg $DEV1NAME $DEV2NAME $DEV3NAME

# create volumes 5T origin and .5T snapshot
time lvcreate --size 5124G -n test testvg
time lvcreate --size 512G -n test_snap testvg

echo "1..7"

zumastor define volume testvol /dev/testvg/test /dev/testvg/test_snap --initialize --mountopts nouuid
mkfs.xfs /dev/mapper/testvol
zumastor define master testvol; zumastor define schedule testvol -h 24 -d 7

echo ok 1 - testvol set up


sync
zumastor snapshot testvol hourly

if timeout_file_wait 120 /var/run/zumastor/snapshot/testvol/hourly.0 ; then
  echo "ok 2 - first snapshot mounted"
else
  ls -lR /var/run/zumastor/
  echo "not ok 2 - first snapshot mounted"
  exit 2
fi

date >> /var/run/zumastor/mount/testvol/testfile

if [ ! -f /var/run/zumastor/snapshot/hourly.0/testfile ] ; then
  echo "ok 3 - testfile not present in first snapshot"
else
  ls -lR /var/run/zumastor
  echo "not ok 3 - testfile not present in first snapshot"
  exit 3
fi

sync
zumastor snapshot testvol hourly

if timeout_file_wait 120 /var/run/zumastor/snapshot/testvol/hourly.1 ; then
  echo "ok 4 - second snapshot mounted"
else
  ls -lR /var/run/zumastor/
  echo "not ok 4 - second snapshot mounted"
  exit 4
fi



if diff -q /var/run/zumastor/mount/testvol/testfile \
    /var/run/zumastor/snapshot/testvol/hourly.0/testfile 2>&1 >/dev/null ; then
  echo "ok 5 - identical testfile immediately after second snapshot"
else
  ls -lR /var/run/zumastor
  echo "not ok 5 - identical testfile immediately after second snapshot"
  exit 5
fi

date >> /var/run/zumastor/mount/testvol/testfile

if ! diff -q /var/run/zumastor/mount/testvol/testfile \
    /var/run/zumastor/snapshot/testvol/hourly.0/testfile 2>&1 >/dev/null ; then
  echo "ok 6 - testfile changed between origin and second snapshot"
else
  ls -lR /var/run/zumastor
  echo "not ok 6 - testfile changed between origin and second snapshot"
  exit 6
fi

# Cleanup
zumastor forget volume testvol
lvremove -f /dev/testvg/test_snap
lvremove -f /dev/testvg/test
vgremove /dev/testvg
pvremove -ff $DEV1NAME
pvremove -ff $DEV2NAME
pvremove -ff $DEV3NAME
echo "ok 7 - cleanup"

exit 0
