#!/bin/bash -x
#
# Write some data to a ddsnap volume, create and delete various snapshots,
# and ensure that the origin and the snapshot always contain the expected
# data.
#
# Copyright 2008 Google Inc.  All rights reserved
# Author: Steve VanDeBogart (vandebo@google.com)

# Test harness parameters
TIMEOUT=300
NUMDEVS=2
DEV1SIZE=4
DEV2SIZE=4

set -e

rc=0
tnum=1
echo "1..29"

volname=testvol

tmp="/tmp"
chunksize="16k"
maxchunks=16
snaps=""
agentsocket=$tmp/control-$$
serversocket=$tmp/server-$$

# Low level routines

snapname () {
	local snap=$1
	if [ "$snap" = "origin" ] || [ "$snap" = "-1" ]; then
		echo "$volname"
	else
		echo "$volname($snap)"
	fi
}

createdevice () {
	local snap=$1
	# We don't do any resizing, so size of origin and snaps is always the same
	local size=$(ddsnap status $serversocket --size)
	echo 0 $size ddsnap $DEV2NAME $DEV1NAME $agentsocket $snap | dmsetup create `snapname $snap`
}

removedevice () {
	dmsetup remove `snapname $1`
}

startddsnap () {
	mkdir -p /var/log/zumastor/$volname
	ddsnap agent $agentsocket
	ddsnap server $DEV2NAME $DEV1NAME $agentsocket $serversocket --logfile /var/log/zumastor/$volname/server.log

	for i in -1 $snaps; do
		createdevice $i
	done
}

stopddsnap () {
	for i in $snaps -1; do
		removedevice $i
	done
	pkill -f "ddsnap"
}

createsnapshot () {
	local snap=$1

	cp $tmp/$volname "$tmp/`snapname $snap`"

	ddsnap create $serversocket $snap
	blockdev --flushbufs /dev/mapper/$volname
	createdevice $snap

	# Keep a list of created snapshots
	snaps="$snaps $snap"

	check
}

delsnapshot () {
    local snap=$1

    checksnap $snap

    rm "$tmp/`snapname $snap`"
	sleep 1
    removedevice $snap
    ddsnap delete $serversocket $snap

    # Keep a list of created snapshots
    snaps=`echo $snaps | sed -e "s/$snap//"`

	check
}

# Testing routines

writedisk () {
	local snap=$1
	local offset=$2
	local string=$3
	local volume=`snapname $snap`
	
	if [ $offset -ge $maxchunks ]; then
		echo "Trying to write more chunks than compared.  Increase maxchunks."
		exit -1
	fi

	yes "$string" | dd of=/dev/mapper/$volume bs=$chunksize count=1 seek=$offset conv=notrunc status=noxfer 2>&1 | grep -v "0 records" || true
	yes "$string" | dd of=$tmp/$volume        bs=$chunksize count=1 seek=$offset conv=notrunc status=noxfer 2>&1 | grep -v "0 records" || true

	if [ -z "$4" ]; then
		check
	fi
}

checksnap () {
	local snap=$1
	local size
	local volume=`snapname $snap`

	dd if=/dev/mapper/$volume of=$tmp/check bs=$chunksize count=$maxchunks status=noxfer 2>&1 | grep -v "0 records" || true
	if diff -q $tmp/check $tmp/$volume; then
		return 0
	fi

	echo "not ok $tnum - $volume differs from what's expected in test $test_desc"
	# Give some detail about how they differ
	ls -l /tmp/check /tmp/$volume
	echo "/tmp/check | uniq -c:"
	cat /tmp/check | uniq -c
	echo "/tmp/$volume | uniq -c:"
	cat /tmp/$volume | uniq -c

	# Clean up the extra devices, but don't forget the volume to allow debugging
	for i in $snaps; do
		removedevice $i
	done
	exit $tnum
}

check () {
	for i in origin $snaps; do
		checksnap $i
	done
}

pass () {
	echo "ok $tnum - $test_desc"
	tnum=$((tnum+1))
}


# Poison the raw devices...
yes "DEADBEEF" | dd of=$DEV1NAME bs=8k 2>/dev/null || true
yes "DEADBEEF" | dd of=$DEV2NAME bs=8k 2>/dev/null || true

rm $tmp/$volname* || true

test_desc="snapshot contains correct data"
# Define the volume
ddsnap initialize -y $DEV2NAME $DEV1NAME 
startddsnap 

# Put the origin in a readable state
for i in `seq  0 $((maxchunks-1))`; do 
	str=`printf "%3d" $i`
	writedisk origin $i "$str" nocheck
done
check

createsnapshot 1
pass

test_desc="origin modification stays on origin"
writedisk origin 1 " +1"
pass

test_desc="snapshot modification stays on snapshot"
writedisk 1 2 " 2s"
pass

test_desc="origin modifications are reproducable"
writedisk origin 7 " +7"
writedisk origin 7 "++7"
pass

test_desc="multiple writes to snapshots with interleaved orgin writes"
writedisk 1 8 " s8"
writedisk origin 8 " +8"
writedisk 1 8 "ss8"
pass

test_desc="write to origin followed by snapshot write works"
writedisk origin 9 " +9"
writedisk 1 9 " s9"
pass

# Prep other tests
test_desc="snapshot 2 ok"
writedisk 1 3 " 3s"
writedisk origin 10 "+10"

createsnapshot 2
pass

test_desc="Write the next snapshot when the previous snapshot is written"
writedisk 2 2 "2ss"
pass

test_desc="Origin write after a snapshot after a written snapshot"
writedisk origin 3 " +3"
pass

test_desc="Now write the second snapshot"
writedisk 2 3 "3ss"
pass

test_desc="Write to second snapshot (1st, 2nd, origin shared)"
writedisk 2 4 " 4s"
pass

test_desc="Then the origin"
writedisk origin 4 " +4"
pass

test_desc="Write to origin (1st, 2nd, origin shared)"
writedisk origin 5 " +5"
pass

test_desc="Then the 2nd snapshot"
writedisk 2 5 " 5s"
pass

test_desc="origin then later snapshots (after initial snapshot)"
writedisk 2 10 "s10"
pass

# Prep future test
test_desc="snapshot 3 ok"
writedisk 2 6 " s6"
writedisk 2 11 "s11"
writedisk origin 12 "+12"

createsnapshot 3
pass

test_desc="Write origin of 3 snapshot series, unshares origin from 1st & 3rd"
writedisk origin 6 " +6"
pass

test_desc="Write 3rd snapshot - unique except shared chunk"
writedisk 3 6 "6ss"
pass

test_desc="Write 2nd snap, create 3rd, write origin, write 1st snap"
writedisk origin 11 "+11"
writedisk 1 11 "r11"
pass

test_desc="Write origin, create 3rd snap, write 2nd snap"
writedisk 2 12 "s12"
pass

# Restart ddsnap to ensure everything got to disk
test_desc="disk image is consistent after a shutdown"
stopddsnap
startddsnap 
check
pass

test_desc="delete old snapshot doesn't screw anything up"
delsnapshot 1
pass

test_desc="delete new snapshot doesn't screw anything up"
delsnapshot 3
pass

test_desc="delete all snapshots doesn't screw anything up"
delsnapshot 2
pass

# test delete a bit more specifically
test_desc="snap1, snap2, origin write, snap1 write, snap3, snap4, snap3 write, del snap3"
createsnapshot 4
createsnapshot 5

writedisk origin 13 "+13"
writedisk 4 13 "s13"

createsnapshot 6
createsnapshot 7

writedisk 6 13 "r13"

delsnapshot 6
pass

test_desc="then write snap4 and origin"
writedisk 7 13 "t13"
writedisk origin 13 "=13"
pass

test_desc="snap1, snap2, snap3, snap4, write snap2, write snap3, write origin, del snap3"
createsnapshot 8

writedisk 5 14 "s14"
writedisk 7 14 "r14"
writedisk origin 14 "+14"

delsnapshot 8
pass

test_desc="then write snap3, origin, snap1"
writedisk 7 14 "t14"
writedisk origin 14 "=14"
writedisk 4 14 "u14"
pass

test_desc="cleanup"
stopddsnap
pass

exit $rc
