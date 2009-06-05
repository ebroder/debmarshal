#!/bin/sh -x
#
# $Id$
#
# Set up a zumastor volume and verify that --zero really zeroes it out.
#
# Copyright 2007-2008 Google Inc.  All rights reserved
# Author: Drake Diedrich (dld@google.com)


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

echo "1..5"

apt-get update

dd if=/dev/urandom bs=512 of=${DEV1NAME} || true
dd if=/dev/urandom bs=512 of=${DEV2NAME} || true
echo ok 1 - raw volumes randomized

zumastor define volume testvol ${DEV1NAME} ${DEV2NAME} --initialize  --zero
echo ok 2 - zumastor volume defined

size=`blockdev --getsize64 /dev/mapper/testvol`
echo ok 3 - got testvol size

if cmp --bytes=$size /dev/mapper/testvol /dev/zero
then
  echo ok 4 - testvol matches /dev/zero
else
  echo not ok 4 - testvol does not match /dev/zero
  exit 4
fi

if zumastor forget volume testvol
then
  echo ok 5 - Cleanup complete
else
  echo not ok 5 - Cleanup not complete
  exit 5
fi

exit 0
