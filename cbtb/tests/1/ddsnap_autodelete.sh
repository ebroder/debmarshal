#!/bin/sh -x
#
# Verify that ddsnap handles snapshot squashing/autodelete correctly.
#
# Copyright 2008 Google Inc.  All rights reserved
# Author: Jiaying Zhang (jiayingz@google.com)

set -e

NUMDEVS=2
DEV1SIZE=8
DEV2SIZE=4

MAXSNAPSHOTS=64

echo "1..10"
apt-get update

ddsnap initialize -y -c 8k $DEV2NAME $DEV1NAME 

ddsnap agent --logfile /tmp/srcagt.log /tmp/src.control
ddsnap server --logfile /tmp/srcsvr.log $DEV2NAME $DEV1NAME /tmp/src.control /tmp/src.server
sleep 3

size=`ddsnap status /tmp/src.server --size`
echo $size
echo 0 $size ddsnap $DEV2NAME $DEV1NAME /tmp/src.control -1 | dmsetup create testvol 
echo "ok 0 - ddsnap volume set up"

ddsnap create /tmp/src.server 0
blockdev --flushbufs /dev/mapper/testvol
echo 0 $size ddsnap $DEV2NAME $DEV1NAME /tmp/src.control 0 | dmsetup create testvol\(0\)

dd if=/dev/mapper/testvol\(0\) of=/dev/null bs=1K count=1 || { echo "not ok 1 - first snapshot accessible"; exit 1; }
dd if=/dev/zero of=/dev/mapper/testvol\(0\) bs=1K count=1 || { echo "not ok 1 - first snapshot accessible"; exit 1; }
echo "ok 1 - first snapshot accessible"

# the snapshot is squashed during this copy
dd if=/dev/zero of=/dev/mapper/testvol bs=1M count=6
sync
ddsnap status /tmp/src.server
ddsnap status --state /tmp/src.server 0 && { echo "not ok 2 - snapshot is squashed"; exit 2; }
echo "ok 2 - snapshot is squashed"

# read or write the squashed snapshot device should fail
dd if=/dev/mapper/testvol\(0\) of=/dev/null bs=1K count=1 && { echo "not ok 3 - squashed snapshot not accessible"; exit 3; }
dd if=/dev/zero of=/dev/mapper/testvol\(0\) bs=1K count=1 && { echo "not ok 3 - squashed snapshot not accessible"; exit 3; }
echo "ok 3 - squashed snapshot not accessible"

dmsetup remove testvol\(0\)
#ddsnap delete /tmp/src.server 0 || { echo "not ok 4 - remove the squashed snapshot"; exit 4; }
echo "ok 4 - remove the squashed snapshot"

# test the autodelte when we exceed 64 snapshot limit
count=1
while [ $count -le $MAXSNAPSHOTS ]; do
	echo count $count
	ddsnap create /tmp/src.server $count || { ddsnap status /tmp/src.server; echo "not ok 5 - ddsnap create"; exit 5; }
	blockdev --flushbufs /dev/mapper/testvol
	echo 0 $size ddsnap $DEV2NAME $DEV1NAME /tmp/src.control $count | dmsetup create testvol\($count\)
	error=$?
	if [ $error -ne 0 ]; then
		echo "not ok 6 - dmsetup create"
		exit 6
	fi
	count=`expr $count + 1`
done
echo "ok 6 - dmsetup create"

# the 'ddsnap create' command below should fail because we exceed the limit
ddsnap create /tmp/src.server $count && echo "ok 7 - exceed $MAXSNAPSHOTS snapshot limit"

# remove an old snapshot client. The snapshot now has zero usecount and will
# be auto deleted when a new snapshot creation request comes
dmsetup remove testvol\(10\)
count=`expr $count + 1`
ddsnap create /tmp/src.server $count || { echo "not ok 8 - zero usecount snapshot auto deleted"; exit 8; }
echo "ok 8 - zero usecount snapshot auto deleted"
blockdev --flushbufs /dev/mapper/testvol
echo 0 $size ddsnap $DEV2NAME $DEV1NAME /tmp/src.control $count | dmsetup create testvol\($count\)
echo "ok 9 - dmsetup create for the new snapshot"

dmsetup ls | grep testvol | awk '{ print $1 }' | xargs -L1 dmsetup remove
pkill -f 'ddsnap agent' || true
echo 'ok 10 - cleanup'

exit 0
