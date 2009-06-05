#!/bin/sh
#
# Verify that zumastor handles snapshot squashing/autodelete correctly.
#
# Copyright 2008 Google Inc.  All rights reserved
# Author: Jiaying Zhang (jiayingz@google.com)

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

# The required sizes of the sdb and sdc devices in M.
NUMDEVS=2
DEV1SIZE=8
DEV2SIZE=4

echo "1..7"

apt-get update
aptitude install -y e2fsprogs

zumastor define volume testvol $DEV1NAME $DEV2NAME --initialize
mkfs.ext3 /dev/mapper/testvol
zumastor define master testvol; zumastor define schedule testvol -h 5

echo ok 1 - testvol set up

date > /var/run/zumastor/mount/testvol/file
sync
zumastor snapshot testvol hourly
if timeout_file_wait 30 /var/run/zumastor/snapshot/testvol/hourly.0 ; then
	echo "ok 2 - first snapshot mounted"
else
	echo "not ok 2 - first snapshot mounted"
	exit 2
fi

# the snapshot is squashed during this copy
dd if=/dev/zero of=/var/run/zumastor/mount/testvol/testfile bs=1M count=6
sync
# access the squashed snapshot device should fail
cat /var/run/zumastor/snapshot/testvol/hourly.0/file && { echo "not ok 3 - access denied on the deleted snapshot"; exit 3; }
echo "ok 3 - access denied on the deleted snapshot"

zumastor status --usage
# test the autodelte when we run out of snapshot space or exceed 64 snapshot limit
count=0
while [ $count -lt 8 ]; do
	echo count $count
	zumastor snapshot testvol hourly
	count=`expr $count + 1`
	sleep 1
done

ddsnap usecount /var/run/zumastor/servers/testvol 2 && { echo "not ok 4 - squashed snapshot not deleted"; exit 4; }
echo "ok 4 - squashed snapshot not deleted"

dd if=/dev/zero of=/var/run/zumastor/mount/testvol/testfile bs=1M count=6
sync
zumastor snapshot testvol hourly
sleep 3
zumastor status --usage
usecount=`ddsnap usecount /var/run/zumastor/servers/testvol 18`
[ $usecount -eq 1 ] || { echo "not ok 5 - snapshot usecount"; exit 5; }
echo "ok 5 - snapshot usecount"

/etc/init.d/zumastor stop
dmsetup ls | grep testvol && { echo "not ok 6 - leaked snapshot device after zumastor stop"; exit 6; }
echo "ok 6 - leaked snapshot device after zumastor stop"

/etc/init.d/zumastor start
zumastor status --usage
zumastor forget volume testvol
dmsetup ls | grep testvol && { echo "not ok 7 - leaked snapshot device after forget volume"; exit 7; }
echo "ok 7 - leaked snapshot device after forget volume"

exit 0
