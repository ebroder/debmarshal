#!/bin/sh -x
#
# $Id$
#
# Make use of large, extra devices on /dev/sdb and /dev/sdc to test
# terabyte-sized zumastor filesystems.  Other than not using LVM and using
# very large devices, this is the same as the snapshot-zumastor.sh test.
# To reduce the runtime of this test, only the XFS filesystem is tested.
# mkfs.ext3 takes on the order of a couple of hours to run under emulation
# on a filesystem of this size.
#
# Copyright 2007 Google Inc.  All rights reserved
# Author: Drake Diedrich (dld@google.com)


set -e

# The required sizes of the sdb and sdc devices in M.  2045G
# Read only by the test harness.
NUMDEVS=2
DEV1SIZE=2094080
DEV2SIZE=2094080
#DEV1NAME=/dev/null
#DEV2NAME=/dev/null

# Terminate test in 40 minutes.  Read by test harness.
TIMEOUT=2400

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



echo "1..6"

apt-get -q -y --force-yes update
apt-get install -q -y --force-yes xfsprogs

mount
ls -l $DEV1NAME $DEV2NAME
zumastor define volume testvol $DEV1NAME $DEV2NAME --initialize --mountopts nouuid
mkfs.xfs -f /dev/mapper/testvol
zumastor define master testvol; zumastor define schedule testvol -h 24 -d 7

echo ok 1 - testvol set up

sync
zumastor snapshot testvol hourly

if timeout_file_wait 30 /var/run/zumastor/snapshot/testvol/hourly.0 ; then
  echo "ok 3 - first snapshot mounted"
else
  ls -lR /var/run/zumastor/
  echo "not ok 3 - first snapshot mounted"
  exit 3
fi

date >> /var/run/zumastor/mount/testvol/testfile

if [ ! -f /var/run/zumastor/snapshot/testvol/hourly.0/testfile ] ; then
  echo "ok 4 - testfile not present in first snapshot"
else
  ls -lR /var/run/zumastor/
  echo "not ok 4 - testfile not present in first snapshot"
  exit 4
fi

sync
zumastor snapshot testvol hourly 


if timeout_file_wait 30 /var/run/zumastor/snapshot/testvol/hourly.1 ; then
  echo "ok 5 - second snapshot mounted"
else
  ls -lR /var/run/zumastor/
  echo "not ok 5 - second snapshot mounted"
  exit 5
fi

  
if diff -q /var/run/zumastor/mount/testvol/testfile \
    /var/run/zumastor/snapshot/testvol/hourly.0/testfile 2>&1 >/dev/null ; then
  echo "ok 6 - identical testfile immediately after second snapshot"
else
  ls -lR /var/run/zumastor/
  echo "not ok 6 - identical testfile immediately after second snapshot"
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

exit 0
