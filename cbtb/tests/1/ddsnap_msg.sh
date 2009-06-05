#!/bin/sh -x
#
# $Id: ddsnap-error-handling.sh 1234 2008-01-05 05:24:09Z jiayingz $
#
# Verify that ddsnap/ddsnapd handle error messages correctly
#
# Copyright 2008 Google Inc.  All rights reserved
# Author: Jiaying Zhang (jiayingz@google.com)

set -e

NUMDEVS=2
DEV1SIZE=8
DEV2SIZE=4
#DEV1NAME=/dev/null
#DEV2NAME=/dev/null

# test combined snapshot and metadata
ddsnap initialize -y -c 16k $DEV1NAME $DEV2NAME

ddsnap agent --logfile /tmp/srcagt.log /tmp/src.control
ddsnap server --logfile /tmp/srcsvr.log $DEV1NAME $DEV2NAME /tmp/src.control /tmp/src.server

size=`ddsnap status /tmp/src.server --size`
echo 0 $size ddsnap $DEV1NAME $DEV2NAME /tmp/src.control -1 | dmsetup create test
ddsnap create /tmp/src.server 0
echo 0 $size ddsnap $DEV1NAME $DEV2NAME /tmp/src.control 0 | dmsetup create test\(0\)

# error message checking
(ddsnap create /tmp/src.server 0 > /tmp/error 2>&1)
grep "snapshot already exists" /tmp/error || { echo "not ok 0 - create error check"; exit -1; }
echo "ok 0 - create error check"
(ddsnap delete /tmp/src.server 1 > /tmp/error 2>&1)
grep "snapshot doesn't exist" /tmp/error || { echo "not ok 1 - delete error check"; exit -1; }
echo "ok 1 - delete error check"
(ddsnap usecount /tmp/src.server 0 -1 > /tmp/error 2>&1)
grep "Usecount underflow" /tmp/error || { echo "not ok 2 - usecount error check"; exit -1; }
echo "ok 2 - usecount error check"
(ddsnap priority /tmp/src.server 1 2 > /tmp/error 2>&1)
grep "Snapshot tag 1 is not valid" /tmp/error || { echo "not ok 3 - priority error check"; exit -1; }
echo "ok 3 - priority error check"
(ddsnap status --size /tmp/src.server 1 > /tmp/error 2>&1)
grep "Snapshot 1 is not valid" /tmp/error || { echo "not ok 4 - size error check"; exit -1; }
echo "ok 4 - size error check"
(ddsnap resize /tmp/src.server -s 3G -m 1G > /tmp/error 2>&1)
grep "snapshot device and metadata device are the same, can't resize them to two values" /tmp/error || { echo "not ok 5 - size error check"; exit -1; }
echo "ok 5 - size error check"

# normal case checking
ddsnap create /tmp/src.server 1 || { echo "not ok 6 - snapshot create"; exit -1; }
echo "ok 6 - snapshot create"
ddsnap usecount /tmp/src.server 0 2 || { echo "not ok 7 - increase usecount"; exit -1; }
echo "ok 7 - increase usecount"
ddsnap usecount /tmp/src.server 0 -2 || { echo "not ok 8 - decrease usecount"; exit -1; }
echo "ok 8 - decrease usecount"
ddsnap priority /tmp/src.server 1 2 || { echo "not ok 9 - set snapshot priority"; exit -1; }
echo "ok 9 - set snapshot priority"
ddsnap status --size /tmp/src.server 1 || { echo "not ok 10 - snapshot size"; exit -1; }
echo "ok 10 - snapshot size"
ddsnap delete /tmp/src.server 1 || { echo "not ok 11 - snapshot delete"; exit -1; }
echo "ok 11 - snapshot delete"
ddsnap status --list /tmp/src.server || { echo "not ok 12 - snapshot list"; exit -1; }
echo "ok 12 - snapshot list"
ddsnap status --state /tmp/src.server 0 || { echo "not ok 13 - snapshot state"; exit -1; }
echo "ok 13 - snapshot state"
ddsnap status /tmp/src.server || { echo "not ok 14 - snapshot status"; exit -1; }
echo "ok 14 - snapshot status"


### Cleanup
dmsetup remove test
dmsetup remove test\(0\)
pkill -f 'ddsnap agent' || true
echo 'ok 15 - cleanup'

exit 0
