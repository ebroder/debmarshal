#!/bin/sh -x
#
# $Id$
#
# Based on replication-zumastor.  Only the slave can ssh to root on the
# master, the master cannot ssh to the slave as root.  Since this is
# not designed at present to work, yet is required to survive compromise
# of the master, it is expected to fail.  The slave can still ssh
# to the master, which will be disabled in a separate test.
#
# Copyright 2007 Google Inc.  All rights reserved
# Author: Drake Diedrich (dld@google.com)


set -e

# Terminate test in 20 minutes.  Read by test harness.
TIMEOUT=1200
NUMDEVS=2
DEV1SIZE=4
DEV2SIZE=8
#DEV1NAME=/dev/null
#DEV2NAME=/dev/null

# why it fails goes here
EXPECT_FAIL=1

slave=${IPADDR2}

SSH='ssh -o StrictHostKeyChecking=no -o BatchMode=yes'
SCP='scp -o StrictHostKeyChecking=no -o BatchMode=yes'


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

# wait for file on remote site with timeout.
timeout_remote_file_wait() {
  local max=$1
  local remote=$2
  local file=$3
  local count=0
  while $SSH $remote [ ! -e $file ] && [ $count -lt $max ]
  do
    count=$(($count + 1))
    sleep 1
  done
  $SSH $remote [ -e $file ]
  return $?
}


echo "1..10"

# set up networking as normal between master and slave
echo ${IPADDR} master >>/etc/hosts
echo ${IPADDR2} slave >>/etc/hosts
hostname master
echo ${IPADDR} master | ${SSH} root@${slave} "cat >>/etc/hosts"
echo ${IPADDR2} slave | ${SSH} root@${slave} "cat >>/etc/hosts"
${SCP} ${HOME}/.ssh/known_hosts root@${slave}:${HOME}/.ssh/known_hosts
${SSH} root@${slave} hostname slave

# create a new root-equivalent account on the slave that the
# master can ssh to for the purpose of running the test.
# Leave zumastor ignorant of this account and delete the authorized_keys
# entry that allows access to root@slave.
$SSH root@${slave} cp -pr /root /testroot
echo testroot::0:0:root:/testroot:/bin/bash | \
  $SSH root@${slave} "cat >>/etc/passwd"
$SSH root@${slave} rm /root/.ssh/authorized_keys


zumastor define volume testvol ${DEV1NAME} ${DEV2NAME} --initialize
mkfs.ext3 /dev/mapper/testvol
zumastor define master testvol; zumastor define schedule testvol -h 24 -d 7
zumastor status --usage
ssh-keyscan -t rsa slave >>${HOME}/.ssh/known_hosts
ssh-keyscan -t rsa master >>${HOME}/.ssh/known_hosts
echo ok 1 - master testvol set up

${SSH} testroot@${slave} zumastor define volume testvol ${DEV1NAME} ${DEV2NAME} --initialize
${SSH} testroot@${slave} zumastor status --usage
echo ok 2 - slave testvol set up

zumastor define target testvol slave -p 30
zumastor status --usage
echo ok 3 - defined target on master

${SSH} testroot@${slave} zumastor define source testvol master --period 600
${SSH} testroot@${slave} zumastor status --usage
echo ok 4 - configured source on target

${SSH} testroot@${slave} zumastor start source testvol
${SSH} testroot@${slave} zumastor status --usage
echo ok 5 - replication started on slave

zumastor replicate testvol --wait slave
zumastor status --usage

# reasonable wait for these small volumes to finish the initial replication
if ! timeout_remote_file_wait 120 testroot${slave} /var/run/zumastor/mount/testvol
then
  $SSH testroot@${slave} "df -h ; mount"
  $SSH testroot@${slave} ls -alR /var/run/zumastor
  $SSH testroot@${slave} zumastor status --usage
  $SSH testroot@${slave} tail -200 /var/log/syslog

  echo not ok 6 - replication manually from master
  exit 6
else
  echo ok 6 - replication manually from master
fi



date >>/var/run/zumastor/mount/testvol/testfile
sync
zumastor snapshot testvol hourly

if ! timeout_file_wait 30 /var/run/zumastor/mount/testvol
then
  ls -alR /var/run/zumastor
  zumastor status --usage
  tail -200 /var/log/syslog
  echo not ok 7 - testfile written, synced, and snapshotted
  exit 7
else
  echo ok 7 - testfile written, synced, and snapshotted
fi

hash=`md5sum /var/run/zumastor/mount/testvol/testfile`

#
# schedule an immediate replication cycle
#
zumastor replicate --wait testvol slave


# give it two minutes to replicate (on a 30 second cycle), and verify
# that it is there.  If not, look at the target volume
if ! timeout_remote_file_wait 120 testroot${slave} /var/run/zumastor/mount/testvol
then
  $SSH testroot@${slave} ls -alR /var/run/zumastor
  $SSH testroot@${slave} zumastor status --usage
  $SSH testroot@${slave} tail -200 /var/log/syslog

  echo not ok 8 - testvol has migrated to slave
  exit 8
else
  echo ok 8 - testvol has migrated to slave
fi

# check separately for the testfile
if ! timeout_remote_file_wait 120 testroot${slave} /var/run/zumastor/mount/testvol/testfile
then
  $SSH testroot@${slave} ls -alR /var/run/zumastor
  $SSH testroot@${slave} zumastor status --usage
  $SSH testroot@${slave} tail -200 /var/log/syslog

  echo not ok 9 - testfile has migrated to slave
  exit 9
else
  echo ok 9 - testfile has migrated to slave
fi

rhash=`${SSH} testroot${slave} md5sum /var/run/zumastor/mount/testvol/testfile` || \
  ${SSH} testroot@${slave} <<EOF
    mount
    df
    ls -lR /var/run/zumastor/
    tail -200 /var/log/syslog
EOF


if [ "$rhash" = "$hash" ] ; then
  echo ok 10 - origin and slave testfiles are in sync
else
  echo not ok 10 - origin and slave testfiles are in sync
    mount
    df
    ls -lR /var/run/zumastor/
    tail -200 /var/log/syslog
  ${SSH} testroot@${slave} <<EOF
    mount
    df
    zumastor status --usage
    ls -lR /var/run/zumastor/
    tail -200 /var/log/syslog
EOF
  exit 10
fi

exit 0
