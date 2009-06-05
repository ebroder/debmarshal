#!/bin/sh -x
#
# $Id: snapshot-zumastor-ext2.sh 1581 2008-04-24 20:27:34Z williamanowak $
#
# Test to make sure there are no files with the same name in
# /proc/driver/ddsnap
# http://code.google.com/p/zumastor/issues/detail?id=126
#
# Copyright 2007-2008 Google Inc.  All rights reserved
# Author: Will Nowak (willn@google.com)


set -e

# The required sizes of the sdb and sdc devices in M.
# Read only by the test harness.
NUMDEVS=2
DEV1SIZE=50
DEV2SIZE=50
#DEV1NAME=/dev/null
#DEV2NAME=/dev/null
# Terminate test in 10 minutes.  Read by test harness.
TIMEOUT=600

echo "1..5"

pvcreate -ff $DEV1NAME
pvcreate -ff $DEV2NAME
vgcreate testvg $DEV1NAME $DEV2NAME
lvcreate -n vol1 -L 4M testvg
lvcreate -n vol1_snap -L 4M testvg
lvcreate -n vol2 -L 4M testvg
lvcreate -n vol2_snap -L 4M testvg
echo ok 1 - lvm setup

zumastor define volume testvol1 /dev/testvg/vol1 /dev/testvg/vol1_snap --initialize
zumastor define master testvol1
zumastor define schedule testvol1 -h 24 -d 7
echo "ok 2 - testvol1 setup"

zumastor define volume testvol2 /dev/testvg/vol2 /dev/testvg/vol2_snap --initialize
zumastor define master testvol2
zumastor define schedule testvol2 -h 24 -d 7
echo "ok 3 - testvol2 setup"

sync

name_frequency=`ls /proc/driver/ddsnap|sort|uniq -c|awk '{ print $1 }'|grep -v 1` || name_frequency=""

if [ "x$name_frequency" = "x" ]
then
  echo "ok 4 - no device appears more than once"
else
  echo "not ok 4 - no device appears more than once"
  ls -l /proc/driver/ddsnap
  exit 4
fi

# cleanup
zumastor forget volume testvol1
zumastor forget volume testvol2
lvremove -f /dev/testvg/vol1
lvremove -f /dev/testvg/vol1_snap
lvremove -f /dev/testvg/vol2
lvremove -f /dev/testvg/vol2_snap
vgremove /dev/testvg
pvremove -ffy $DEV1NAME || true
pvremove -ffy $DEV2NAME || true
echo "ok 5 - cleanup"

exit 0
