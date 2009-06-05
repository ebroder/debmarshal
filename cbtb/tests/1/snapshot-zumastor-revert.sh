#!/bin/sh -x
#
# $Id: snapshot-zumastor-ext3-resize.sh 1189 2007-12-22 00:27:19Z jiahotcake $
#
# Set up testvg with origin and snapshot store, resize origin/snapshot volumes,
# verify resize succeeds and data on origin/snapshot volumes still valid after resizing
#
# Copyright 2007 Google Inc.  All rights reserved
# Author: Jiaying Zhang (jiayingz@google.com)


set -e

# The required sizes of the sdb and sdc devices in M.
# Read only by the test harness.
NUMDEVS=2
DEV1SIZE=4
DEV2SIZE=8
#DEV1NAME=/dev/null
#DEV2NAME=/dev/null

# Terminate test in 10 minutes.  Read by test harness.
TIMEOUT=600

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

echo "1..8"

apt-get update
aptitude install -y e2fsprogs

zumastor define volume testvol $DEV1NAME $DEV2NAME --initialize
mkfs.ext3 /dev/mapper/testvol
zumastor define master testvol; zumastor define schedule testvol -h 24 -d 7

echo ok 1 - testvol set up

date >> /var/run/zumastor/mount/testvol/testfile
sync
zumastor snapshot testvol hourly

if timeout_file_wait 120 /var/run/zumastor/snapshot/testvol/hourly.0 ; then
  echo "ok 2 - first snapshot mounted"
else
  ls -laR /var/run/zumastor/mount
  echo "not ok 2 - first snapshot mounted"
  exit 2
fi

date >> /var/run/zumastor/mount/testvol/testfile
sync

if ! diff -q /var/run/zumastor/mount/testvol/testfile \
	/var/run/zumastor/snapshot/testvol/hourly.0/testfile 2>&1 >/dev/null ; then
  echo "ok 3 - testfile changed between origin and snapshot"
else
  echo "not ok 3 - testfile changed between origin and second snapshot"
  cat /var/run/zumastor/mount/testvol/testfile
  cat /var/run/zumastor/snapshot/testvol/hourly.0/testfile
  exit 3
fi

zumastor snapshot testvol hourly

if timeout_file_wait 120 /var/run/zumastor/snapshot/testvol/hourly.1 ; then
  echo "ok 4 - second snapshot mounted"
else
  ls -laR /var/run/zumastor/mount
  echo "not ok 4 - second snapshot mounted"
  exit 4
fi

if diff -q /var/run/zumastor/mount/testvol/testfile \
	/var/run/zumastor/snapshot/testvol/hourly.0/testfile 2>&1 >/dev/null ; then
  echo "ok 5 - identical testfile after second snapshot"
else
  echo "not ok 5 - identical testfile after second snapshot"
  exit 5
fi

zumastor stop master testvol
zumastor revert testvol 0
zumastor start master testvol

if ! diff -q /var/run/zumastor/mount/testvol/testfile \
	/var/run/zumastor/snapshot/testvol/hourly.0/testfile 2>&1 >/dev/null ; then
  echo "ok 6 - testfile changed between origin and second snapshot after revert"
else
  echo "not ok 6 - testfile changed between origin and second snapshot after revert"
  exit 6
fi

if diff -q /var/run/zumastor/mount/testvol/testfile \
	/var/run/zumastor/snapshot/testvol/hourly.1/testfile 2>&1 >/dev/null ; then
  echo "ok 7 - testfile changed backup to version of the first snapshot"
else
  zumastor status
  diff /var/run/zumastor/mount/testvol/testfile /var/run/zumastor/snapshot/testvol/hourly.1/testfile
  echo "not ok 7 - testfile changed backup to version of the first snapshot"
  exit 7
fi

## Cleanup
zumastor forget volume testvol
echo 'ok 8 - cleanup'

exit 0
