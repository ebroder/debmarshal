#!/bin/sh -x
#
# $Id$
#
# A test of simultaneous snapshots and replication.  This is not
# supported, and an issue is filed, so this test is expected to fail.
# Most likely the test will need to change to match the new configuration
# commands that will be part of adding this feature.
#
# http://code.google.com/p/zumastor/issues/detail?id=26
#
# Copyright 2007 Google Inc.  All rights reserved
# Author: Drake Diedrich (dld@google.com)


set -e

# Terminate test in 5 minutes.  Read by test harness.  The test usually
# times out due to the zumastor define source in step 4, so a very tight
# limit has been given to this test to speed up runs of the entire suite.
TIMEOUT=300
NUMDEVS=2
DEV1SIZE=4
DEV2SIZE=8
#DEV1NAME=/dev/null
#DEV2NAME=/dev/null

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


echo "1..13"

echo ${IPADDR} master >>/etc/hosts
echo ${IPADDR2} slave >>/etc/hosts
hostname master
zumastor define volume testvol ${DEV1NAME} ${DEV2NAME} --initialize
mkfs.ext3 /dev/mapper/testvol
zumastor define master testvol; zumastor define schedule testvol -h 24 -d 7
zumastor status --usage
ssh-keyscan -t rsa slave >>${HOME}/.ssh/known_hosts
ssh-keyscan -t rsa master >>${HOME}/.ssh/known_hosts
echo ok 1 - master testvol set up

echo ${IPADDR} master | ${SSH} root@${slave} "cat >>/etc/hosts"
echo ${IPADDR2} slave | ${SSH} root@${slave} "cat >>/etc/hosts"
${SCP} ${HOME}/.ssh/known_hosts root@${slave}:${HOME}/.ssh/known_hosts
${SSH} root@${slave} hostname slave
${SSH} root@${slave} zumastor define volume testvol ${DEV1NAME} ${DEV2NAME} --initialize
${SSH} root@${slave} zumastor status --usage
echo ok 2 - slave testvol set up

zumastor define target testvol slave -p 30
zumastor status --usage
echo ok 3 - defined target on master

${SSH} root@${slave} zumastor define source testvol master --period 600 -m
${SSH} root@${slave} zumastor define schedule testvol -h 24 -d 7
${SSH} root@${slave} zumastor status --usage
echo ok 4 - configured source on target

${SSH} root@${slave} zumastor start source testvol
${SSH} root@${slave} zumastor status --usage
echo ok 5 - replication started on slave

$SSH root@${slave} 'zumastor snapshot testvol hourly'
zumastor replicate testvol --wait slave
zumastor status --usage

# reasonable wait for these small volumes to finish the initial replication
if ! timeout_remote_file_wait 120 root@${slave} /var/run/zumastor/mount/testvol
then
  $SSH root@${slave} "df -h ; mount"
  $SSH root@${slave} ls -alR /var/run/zumastor
  $SSH root@${slave} zumastor status --usage
  $SSH root@${slave} tail -200 /var/log/syslog

  echo not ok 6 - replication manually from master
  exit 6
else
  echo ok 6 - replication manually from master
fi

# take a snapshot of the empty volume on the slave and wait for it
slavehourly0=/var/run/zumastor/snapshot/testvol/hourly.0
if ! timeout_remote_file_wait 30 root@${slave} $slavehourly0
then
  $SSH root@${slave} "df -h ; mount"
  $SSH root@${slave} ls -alR /var/run/zumastor
  $SSH root@${slave} zumastor status --usage
  $SSH root@${slave} tail -200 /var/log/syslog

  echo not ok 7 - first slave snapshot
  exit 7
else
  slavesnap0=`$SSH root@${slave} "readlink $slavehourly0"`
  echo ok 7 - first slave snapshot
fi

date >>/var/run/zumastor/mount/testvol/testfile
sync
zumastor snapshot testvol hourly

if ! timeout_file_wait 30 /var/run/zumastor/mount/testvol
then
  ls -alR /var/run/zumastor
  zumastor status --usage
  tail -200 /var/log/syslog
  echo not ok 8 - testfile written, synced, and snapshotted
  exit 8
else
  echo ok 8 - testfile written, synced, and snapshotted
fi

hash=`md5sum /var/run/zumastor/mount/testvol/testfile|cut -f1 -d\ `

$SSH root@${slave} zumastor snapshot testvol hourly
#
# schedule an immediate replication cycle
#
zumastor replicate --wait testvol slave


# give it two minutes to replicate (on a 30 second cycle), and verify
# that it is there.  If not, look at the target volume
if ! timeout_remote_file_wait 120 root@${slave} /var/run/zumastor/mount/testvol
then
  $SSH root@${slave} ls -alR /var/run/zumastor
  $SSH root@${slave} zumastor status --usage
  $SSH root@${slave} tail -200 /var/log/syslog

  echo not ok 9 - testvol has migrated to slave
  exit 9
else
  echo ok 9 - testvol has migrated to slave
fi

# check separately for the testfile
if ! timeout_remote_file_wait 120 root@${slave} /var/run/zumastor/mount/testvol/testfile
then
  $SSH root@${slave} ls -alR /var/run/zumastor
  $SSH root@${slave} zumastor status --usage
  $SSH root@${slave} tail -200 /var/log/syslog

  echo not ok 10 - testfile has migrated to slave
  exit 10
else
  echo ok 10 - testfile has migrated to slave
fi

rhash=`${SSH} root@${slave} md5sum /var/run/zumastor/mount/testvol/testfile|cut -f1 -d\ ` || \
  ${SSH} root@${slave} <<EOF
    mount
    df
    ls -lR /var/run/zumastor/
    tail -200 /var/log/syslog
EOF


if [ "$rhash" = "$hash" ] ; then
  echo ok 11 - origin and slave testfiles are in sync
else
  echo not ok 11 - origin and slave testfiles are in sync
    mount
    df
    ls -lR /var/run/zumastor/
    tail -200 /var/log/syslog
  ${SSH} root@${slave} <<EOF
    mount
    df
    zumastor status --usage
    ls -lR /var/run/zumastor/
    tail -200 /var/log/syslog
EOF
  exit 11
fi


if ! timeout_remote_file_wait 30 root@${slave} \
  /var/run/zumastor/snapshot/testvol/hourly.1
then
  $SSH root@${slave} "df -h ; mount"
  $SSH root@${slave} ls -alR /var/run/zumastor
  $SSH root@${slave} zumastor status --usage
  $SSH root@${slave} tail -200 /var/log/syslog

  echo not ok 12 - second slave snapshot
  exit 12
else
  echo ok 12 - second slave snapshot
fi


rhash0=`${SSH} root@${slave} md5sum /var/run/zumastor/snapshot/testvol/hourly.0/testfile|cut -f1 -d\ ` || \
  ${SSH} root@${slave} <<EOF
    mount
    df
    ls -lR /var/run/zumastor/
    tail -200 /var/log/syslog
EOF

# cleanup
zumastor forget volume testvol
${SSH} root@${slave} zumastor forget volume testvol
echo "ok 13 - cleanup"

exit 0
