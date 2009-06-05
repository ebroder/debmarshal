#!/bin/sh -x
#
# $Id$
#
# Use ddsnap directly to create a snapshot, modify the origin, and create
# another snapshot.  Verify that checksums change and remain correct.
#
# Copyright 2007 Google Inc.  All rights reserved
# Author: Drake Diedrich (dld@google.com)


set -e

rc=0


# Terminate test in 20 minutes.  Read by test harness.
TIMEOUT=1200

# Extra disk sizes required
NUMDEVS=2
DEV1SIZE=4
DEV2SIZE=8
#DEV1NAME=/dev/null
#DEV2NAME=/dev/null

slave=${IPADDR2}
SSH='ssh -o StrictHostKeyChecking=no -o BatchMode=yes'
SCP='scp -o StrictHostKeyChecking=no -o BatchMode=yes'


# necessary at the moment, ddsnap just sends requests and doesn't wait
SLEEP=10

echo "1..30"

echo ${IPADDR} master >>/etc/hosts
echo ${IPADDR2} slave >>/etc/hosts
hostname master
ssh-keyscan -t rsa slave >>${HOME}/.ssh/known_hosts
ssh-keyscan -t rsa master >>${HOME}/.ssh/known_hosts
echo ok 1 - master network set up

echo ${IPADDR} master | ${SSH} root@${slave} "cat >>/etc/hosts"
echo ${IPADDR2} slave | ${SSH} root@${slave} "cat >>/etc/hosts"
${SCP} ${HOME}/.ssh/known_hosts root@${slave}:${HOME}/.ssh/known_hosts
${SSH} root@${slave} hostname slave
echo ok 2 - slave network set up


ddsnap initialize ${DEV2NAME} ${DEV1NAME}
echo ok 5 - master ddsnap initialize

controlsocket="/tmp/control"
ddsnap agent $controlsocket
echo ok 6 - master ddsnap agent
sleep $SLEEP

volname=testvol
mkdir /tmp/server
# TODO: when b/892805 is fixed, last element of socket may be something
# other than $volname
serversocket="/tmp/server/$volname"
ddsnap server ${DEV2NAME} ${DEV1NAME} $controlsocket $serversocket
echo ok 7 - master ddsnap server
sleep $SLEEP

${SSH} root@${slave} ddsnap initialize ${DEV2NAME} ${DEV1NAME}
echo ok 8 - slave ddsnap initialize
sleep $SLEEP

${SSH} root@${slave} ddsnap agent $controlsocket
echo ok 9 - slave ddsnap agent
sleep $SLEEP

${SSH} root@${slave} mkdir /tmp/server
${SSH} root@${slave} \
  ddsnap server ${DEV2NAME} ${DEV1NAME} $controlsocket $serversocket
echo ok 10 - slave ddsnap server
sleep $SLEEP

size=`ddsnap status $serversocket --size`
echo 0 $size ddsnap ${DEV2NAME} ${DEV1NAME} $controlsocket -1 | dmsetup create $volname
echo ok 11 - master create $volname
sleep $SLEEP

$SSH root@${slave} "echo 0 $size ddsnap ${DEV2NAME} ${DEV1NAME} $controlsocket -1 | dmsetup create $volname"
echo ok 12 - slave create $volname
sleep $SLEEP

listenport=3333
$SSH root@${slave} \
  ddsnap delta listen /dev/mapper/$volname ${slave}:${listenport}
echo ok 13 - slave ddsnap delta listening for snapshot deltas
sleep $SLEEP


tosnap=0
ddsnap create $serversocket $tosnap
echo ok 14 - ddsnap create $tosnap
sleep $SLEEP

echo 0 $size ddsnap ${DEV2NAME} ${DEV1NAME} \
  $controlsocket $tosnap | \
  dmsetup create $volname\($tosnap\)
echo ok 15 - create $volname\($tosnap\) block device on master
sleep $SLEEP

hash=`md5sum </dev/mapper/$volname`
hash0=`md5sum </dev/mapper/$volname\($tosnap\)`
if [ "$hash" != "$hash0" ] ; then
  echo "not "
  rc=16
fi
echo ok 16 - $volname==$volname\($tosnap\)
sleep $SLEEP

ddsnap transmit $serversocket ${slave}:$listenport $tosnap
echo ok 17 - snapshot $tosnap transmitting to slave origin
sleep $SLEEP

$SSH root@$slave \
  ddsnap create $serversocket $tosnap
echo ok 18 - create snapshot $tosnap on slave
sleep $SLEEP

$SSH root@$slave \
  "echo 0 $size ddsnap ${DEV2NAME} ${DEV1NAME} $controlsocket $tosnap | dmsetup create $volname\($tosnap\)"
echo ok 19 - create $volname\($tosnap\) block device on slave

hash0slave=`$SSH root@$slave "md5sum </dev/mapper/$volname\($tosnap\)"`
if [ "$hash0" != "$hash0slave" ] ; then
  echo "not "
  rc=20
fi
echo ok 20 - master $volname\($tosnap\) == slave $volname\($tosnap\)


dd if=/dev/urandom bs=32k count=128 of=/dev/mapper/$volname
echo 21 - copy random data onto master $volname

fromsnap=0
tosnap=2
ddsnap create $serversocket $tosnap
echo ok 22 - ddsnap create $tosnap
sleep $SLEEP

echo 0 $size ddsnap ${DEV2NAME} ${DEV1NAME} \
  $controlsocket $tosnap | \
  dmsetup create $volname\($tosnap\)
echo ok 23 - create $volname\($tosnap\) block device on master

hash=`md5sum </dev/mapper/$volname`
hash2=`md5sum </dev/mapper/$volname\($tosnap\)`
if [ "$hash" != "$hash2" ] ; then
  echo "not "
  rc=24
fi
echo ok 24 - $volname==$volname\($tosnap\)


ddsnap transmit $serversocket ${slave}:$listenport $fromsnap $tosnap
echo ok 25 - delta from $fromsnap to $tosnap transmitting to slave origin
sleep $SLEEP

$SSH root@$slave \
  ddsnap create $serversocket $tosnap
echo ok 26 - create snapshot $tosnap on slave

$SSH root@$slave \
  "echo 0 $size ddsnap ${DEV2NAME} ${DEV1NAME} $controlsocket $tosnap | dmsetup create $volname\($tosnap\)"
echo ok 27 - create $volname\($tosnap\) block device on slave

hash2slave=`$SSH root@$slave "md5sum </dev/mapper/$volname\($tosnap\)"`
if [ "$hash2" != "$hash2slave" ] ; then
  echo "not "
  rc=28
fi
echo ok 28 - master $volname\($tosnap\) == slave $volname\($tosnap\)

$SSH root@$slave "dmsetup remove $volname\(2\)"
$SSH root@$slave "dmsetup remove $volname\(0\)"
$SSH root@$slave "dmsetup remove $volname"
dmsetup remove $volname\(2\)
dmsetup remove $volname\(0\)
dmsetup remove $volname
echo ok 29 - remove master and slave device mappings


ddsnap delete $serversocket 2
ddsnap delete $serversocket 0
$SSH root@$slave ddsnap delete $serversocket 2
$SSH root@$slave ddsnap delete $serversocket 0
echo ok 30 - delete ddsnap snapshots on master and slave

# TODO: if ddsnap gets a native method to shut down, test it.  Leave out
# using pkill to test shutdown for now.  Without pkill this will verify
# that a system can shut down with ddsnap daemons still running.

exit $rc

