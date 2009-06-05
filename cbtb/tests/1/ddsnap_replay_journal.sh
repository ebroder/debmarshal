#!/bin/sh -x
#
# Verify ddsnap journal replay works correctly when
# 'ddsnap server' restarts after an unclean exit
#
# Copyright 2008 Google Inc.  All rights reserved
# Author: Jiaying Zhang (jiayingz@google.com)

set -e

EXPECT_FAIL=1

NUMDEVS=2
DEV1SIZE=32
DEV2SIZE=32

echo "1..5"  # Five checking steps in this test

CHUNK_SIZES="512 1k 2k 4k 8k 16k 32k 64k 128k 256k 512k 1m"
for chunksize in $CHUNK_SIZES; do
	# these three environment variables are read by ddsnapd for fault injection
	export DDSNAP_ACTION="abort"
	export DDSNAP_TRIGGER="SHUTDOWN_SERVER"
	export DDSNAP_COUNT=1

	[ -e /tmp/srcsvr.log ] && rm /tmp/srcsvr.log
	ddsnap initialize -y -c $chunksize $DEV1NAME $DEV2NAME

	ddsnap agent --logfile /tmp/srcagt.log /tmp/src.control
	ddsnap server --logfile /tmp/srcsvr.log $DEV1NAME $DEV2NAME /tmp/src.control /tmp/src.server -X -D
	sleep 3

	size=`ddsnap status /tmp/src.server --size`
	echo $size
	echo 0 $size ddsnap $DEV1NAME $DEV2NAME /tmp/src.control -1 | dmsetup create testvol

	ddsnap create /tmp/src.server 0
	blockdev --flushbufs /dev/mapper/testvol
	echo 0 $size ddsnap $DEV1NAME $DEV2NAME /tmp/src.control 0 | dmsetup create testvol\(0\)

	echo "ok 1 - ddsnap snapshot set up"

	dd if=/dev/zero of=/dev/mapper/testvol bs=1K count=1000 || exit 2
	sync
	pkill -f "ddsnap server"

	# clean up the fault injection
	export DDSNAP_ACTION=
	export DDSNAP_TRIGGER=
	export DDSNAP_COUNT=

	# restart ddsnap server which will run journal replay
	ddsnap agent --logfile /tmp/srcagt.log /tmp/src.control
	ddsnap server --logfile /tmp/srcsvr.log $DEV1NAME $DEV2NAME /tmp/src.control /tmp/src.server
	sleep 3

	cat /tmp/srcsvr.log

	grep "Replaying journal" /tmp/srcsvr.log || { echo "not ok 2 - journal replay triggered"; exit 2; }
	echo "ok 2 - journal replay triggered"

	grep "count wrong" /tmp/srcsvr.log && { echo "not ok 3 - freechunk check after journal replay"; exit 3; }
	echo "ok 3 - freechunk check after journal replay"

	grep "Journal recovery failed" /tmp/srcsvr.log && { echo "not ok 4 - journal replay succeeds"; exit 4; }
	echo "ok 4 - journal replay succeeds"

	pgrep ddsnap || { echo "not ok 5 - ddsnap server is running"; exit 5; }
	echo "ok 5 - ddsnap server is running";

	dmsetup remove testvol\(0\)
	dmsetup remove testvol
	pkill -f "ddsnap agent"
	echo 'ok 5 - cleanup'

done
exit 0
