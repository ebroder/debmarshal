#!/bin/sh -x
#
# test multi-layer replication.
#
# http://code.google.com/p/zumastor/issues/detail?id=27
# Copyright 2008 Google Inc.  All rights reserved
# Author: Jiaying Zhang (jiayingz@google.com)

set -e

# Terminate test in 10 minutes.
TIMEOUT=600
NUMDEVS=2
DEV1SIZE=4
DEV2SIZE=8
#DEV1NAME=/dev/null
#DEV2NAME=/dev/null

# Feature request.  http://code.google.com/p/zumastor/issues/detail?id=27
EXPECT_FAIL=1


slave1=${IPADDR2}
slave2=${IPADDR3}

SSH='ssh -o StrictHostKeyChecking=no -o BatchMode=yes'
SCP='scp -o StrictHostKeyChecking=no -o BatchMode=yes'

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


echo "1..8"

echo ${IPADDR} master >>/etc/hosts
echo ${IPADDR2} slave1 >>/etc/hosts
echo ${IPADDR3} slave2 >>/etc/hosts
hostname master
zumastor define volume testvol ${DEV1NAME} ${DEV2NAME} --initialize
mkfs.ext3 /dev/mapper/testvol
zumastor define master testvol; zumastor define schedule testvol -h 24 -d 7
zumastor status --usage
echo ok 1 - master testvol set up

ssh-keyscan -t rsa slave1 >>${HOME}/.ssh/known_hosts
ssh-keyscan -t rsa slave2 >>${HOME}/.ssh/known_hosts
ssh-keyscan -t rsa master >>${HOME}/.ssh/known_hosts

echo ${IPADDR} master | ${SSH} root@${slave1} "cat >>/etc/hosts"
echo ${IPADDR2} slave1 | ${SSH} root@${slave1} "cat >>/etc/hosts"
echo ${IPADDR3} slave2 | ${SSH} root@${slave1} "cat >>/etc/hosts"
${SCP} ${HOME}/.ssh/known_hosts root@${slave1}:${HOME}/.ssh/known_hosts
${SSH} root@${slave1} hostname slave1
${SSH} root@${slave1} zumastor define volume testvol ${DEV1NAME} ${DEV2NAME} --initialize
${SSH} root@${slave1} zumastor status --usage
echo ok 2 - slave1 testvol set up

echo ${IPADDR} master | ${SSH} root@${slave2} "cat >>/etc/hosts"
echo ${IPADDR2} slave1 | ${SSH} root@${slave2} "cat >>/etc/hosts"
echo ${IPADDR3} slave2 | ${SSH} root@${slave2} "cat >>/etc/hosts"
${SCP} ${HOME}/.ssh/known_hosts root@${slave2}:${HOME}/.ssh/known_hosts
${SSH} root@${slave2} hostname slave2
${SSH} root@${slave2} zumastor define volume testvol ${DEV1NAME} ${DEV2NAME} --initialize
${SSH} root@${slave2} zumastor status --usage
echo ok 3 - slave2 testvol set up

zumastor define target testvol slave1 -p 30
zumastor status --usage
${SSH} root@${slave1} zumastor define source testvol master --period 600
${SSH} root@${slave1} zumastor define target testvol slave2 -p 30
${SSH} root@${slave1} zumastor status --usage
${SSH} root@${slave2} zumastor define source testvol slave1 --period 600
${SSH} root@${slave2} zumastor status --usage
echo ok 4 - chained replication set up

zumastor replicate testvol --wait slave1
zumastor status --usage

# reasonable wait for these small volumes to finish the initial replication
if ! timeout_remote_file_wait 180 root@${slave2} /var/run/zumastor/mount/testvol
then
  df -h ; mount
  ls -alR /var/run/zumastor
  zumastor status --usage
  $SSH root@${slave1} "df -h ; mount"
  $SSH root@${slave1} ls -alR /var/run/zumastor
  $SSH root@${slave1} zumastor status --usage
  $SSH root@${slave2} "df -h ; mount"
  $SSH root@${slave2} ls -alR /var/run/zumastor
  $SSH root@${slave2} zumastor status --usage

  echo not ok 5 - initial replication reaches the second target
  exit 5
else
  echo ok 5 - initial replication reaches the second target
fi

date >>/var/run/zumastor/mount/testvol/testfile
sync
zumastor replicate --wait testvol slave1
# reasonable wait for the written file to be replicated to the second target
if ! timeout_remote_file_wait 180 root@${slave2} /var/run/zumastor/mount/testvol/testfile
then
  ls -alR /var/run/zumastor
  zumastor status --usage
  $SSH root@${slave1} "ls -alR /var/run/zumastor"
  $SSH root@${slave1} zumastor status --usage
  $SSH root@${slave2} "ls -alR /var/run/zumastor"
  $SSH root@${slave2} zumastor status --usage

  echo not ok 6 - written file replicated to the second target
  exit 6
else
  echo ok 6 - written file replicated to the second target
fi

hash=`md5sum /var/run/zumastor/mount/testvol/testfile`

rhash=`${SSH} root@${slave1} md5sum /var/run/zumastor/mount/testvol/testfile` || \
  ${SSH} root@${slave1} <<EOF
    mount
    df
    ls -lR /var/run/zumastor/
    tail -200 /var/log/syslog
EOF

if [ "$rhash" = "$hash" ] ; then
  echo ok 7 - master and slave1 testfiles are in sync
else
  echo not ok 7 - master and slave1 testfiles are in sync
  exit 7
fi

rhash=`${SSH} root@${slave2} md5sum /var/run/zumastor/mount/testvol/testfile` || \
  ${SSH} root@${slave2} <<EOF
    mount
    df
    ls -lR /var/run/zumastor/
    tail -200 /var/log/syslog
EOF

if [ "$rhash" = "$hash" ] ; then
  echo ok 8 - master and slave2 testfiles are in sync
else
  echo not ok 8 - master and slave2 testfiles are in sync
  exit 8
fi

exit 0
