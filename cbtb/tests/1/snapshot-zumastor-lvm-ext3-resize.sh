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
NUMDEVS=1
DEV1SIZE=1024
#DEV1NAME=/dev/null

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

file_check() {
  if diff -q /var/run/zumastor/mount/testvol/testfile \
      /var/run/zumastor/snapshot/testvol/hourly.0/testfile 2>&1 >/dev/null ; then
    echo "ok $1 - $2"
  else
    ls -lR /var/run/zumastor/mount
    echo "not ok $1 - $2"
    exit $1
  fi
}

size_check() {
  if [ $1 = "origin" ]; then
  	realsize=`ddsnap status /var/run/zumastor/servers/testvol | awk '/Origin size:/ { print $3 }'`
  else
  	realsize=`ddsnap status /var/run/zumastor/servers/testvol | awk '/Snapshot store/ { print $9 }'`
  fi
  if [ $realsize = $2 ]; then
    echo "ok $3 - $4"
  else
    echo "not ok $3 - $4"
    exit $3
  fi
}

snapshot_size_check() {
  local id=$1
  if [ $id -eq -1 ]; then
    snapsize=`blockdev --getsize /dev/mapper/testvol`
  else
    snapsize=`blockdev --getsize /dev/mapper/testvol\($id\)`
  fi
  if [ $snapsize = $2 ]; then
    echo "ok $3 - $4"
  else
    echo "not ok $3 - $4"
    exit $3
  fi
}

apt-get update
aptitude install -y e2fsprogs

# create LVM VG testvg
time pvcreate -ff $DEV1NAME
time vgcreate testvg $DEV1NAME

# create volumes 8M origin and 8M snapshot
time lvcreate --size 8M -n test testvg
time lvcreate --size 8M -n test_snap testvg

echo "1..17"

zumastor define volume testvol /dev/testvg/test /dev/testvg/test_snap --initialize

mkfs.ext3 /dev/mapper/testvol
zumastor define master testvol -s; zumastor define schedule testvol -h 24 -d 7

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

file_check 3 "identical testfile after snapshot"

# test origin volume enlarge
lvresize /dev/testvg/test -L 16m
zumastor stop master testvol
zumastor resize testvol --origin 16m
e2fsck -f -y /dev/mapper/testvol
resize2fs /dev/mapper/testvol 16m
zumastor start master testvol
size_check "origin" "16,777,216" 4 "size check after origin volume enlarge"
file_check 5 "testfile changed after origin volume enlarge"
# the size of the old snapshot should not change
snapshot_size_check -1 32768 6 "origin volume size check after origin volume enlarge"
snapshot_size_check 0 16384 7 "old snapshot size check after origin volume enlarge"

# test snapshot store enlarge
lvresize /dev/testvg/test_snap -L 64m
zumastor resize testvol --snapshot 64m
# 1024 is the number of snapshot blocks with the defaul block size 16k
size_check "snap" "4,096" 8 "size check after snapshot store enlarge"
file_check 9 "testfile changed after snapshot store enlarge"
# we will have two snapshots mounted if snapshot enlarging succeeds
# otherwise, ddsnap server will automatically delete the old snapshot
dd if=/dev/zero of=/var/run/zumastor/mount/testvol/zerofile bs=1k count=12k
sync
zumastor snapshot testvol hourly
if timeout_file_wait 120 /var/run/zumastor/snapshot/testvol/hourly.1 ; then
  echo "ok 10 - two snapshots are mounted"
else
  ls -laR /var/run/zumastor/mount
  echo "not ok 10 - two snapshots are mounted"
  exit 2
fi
rm -f /var/run/zumastor/mount/testvol/zerofile
sync

# test origin volume shrink
zumastor stop master testvol
e2fsck -f -y /dev/mapper/testvol
resize2fs /dev/mapper/testvol 4m
# force any data left on the freed space to be copied out to the snapstore
dd if=/dev/zero of=/dev/mapper/testvol bs=1k seek=4k count=12k
sync
zumastor resize testvol --origin 4m
echo y | lvresize /dev/testvg/test -L 4m
zumastor start master testvol
size_check "origin" "4,194,304" 11 "size check after origin volume shrink"
file_check 12 "testfile changed after origin volume shrink"
snapshot_size_check -1 8192 13 "origin volume size check after origin volume shrink"
snapshot_size_check 0 16384 14 "old snapshot size check after origin volume shrink"
snapshot_size_check 2 32768 15 "old snapshot size check after origin volume shrink"

# test snapshot store shrink
zumastor resize testvol --snapshot 32m
echo y | lvresize /dev/testvg/test_snap -L 32m
size_check "snap" "2,048" 16 "size check after snapshot store shrink"
file_check 17 "testfile changed after snapshot store shrink"

## Cleanup
zumastor forget volume testvol
yes | lvremove /dev/testvg/test_snap
yes | lvremove /dev/testvg/test
yes | vgremove testvg
#TODO: Fix this
#yes | pvremove ${DEV1NAME}
echo 'ok 18 - cleanup'

exit 0
