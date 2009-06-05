#!/bin/sh -x
#
# $Id: replication-zumastor-lvm-resize.sh 1189 2008-2-12 00:27:19Z jiahotcake $
#
# Set up testvg with origin and snapshot store, resize origin/snapshot volumes,
# verify replication still works after resizing
#
# Copyright 2008 Google Inc.  All rights reserved
# Author: Jiaying Zhang (jiayingz@google.com)

set -e

# The required sizes of the sdb and sdc devices in M.
# Read only by the test harness.
NUMDEVS=1
DEV1SIZE=1024
#DEV1NAME=/dev/null

# Terminate test in 10 minutes.  Read by test harness.
TIMEOUT=600

slave=${IPADDR2}

SSH='ssh -o StrictHostKeyChecking=no -o BatchMode=yes'
SCP='scp -o StrictHostKeyChecking=no -o BatchMode=yes'

file_check() {
  hash=`md5sum /var/run/zumastor/mount/testvol/testfile`

  rhash=`${SSH} root@${slave} md5sum /var/run/zumastor/mount/testvol/testfile` || \
  ${SSH} root@${slave} <<EOF
      mount
      df
      ls -lR /var/run/zumastor/
      tail -200 /var/log/syslog
EOF

  if [ "$rhash" = "$hash" ] ; then
    echo ok $1 - $2
  else
    echo not ok $1 - $2
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
    exit $1
  fi
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

apt-get update
aptitude install -y e2fsprogs

echo "1..8"

pvcreate -ff ${DEV1NAME}
vgcreate testvg ${DEV1NAME}
lvcreate --size 16M -n test testvg
lvcreate --size 16M -n test_snap testvg

echo ${IPADDR} master >>/etc/hosts
echo ${IPADDR2} slave >>/etc/hosts
hostname master
zumastor define volume testvol /dev/testvg/test /dev/testvg/test_snap --initialize
mkfs.ext3 /dev/mapper/testvol
zumastor define master testvol; zumastor define schedule testvol -h 24 -d 7
zumastor status --usage
ssh-keyscan -t rsa slave >>${HOME}/.ssh/known_hosts
ssh-keyscan -t rsa master >>${HOME}/.ssh/known_hosts
echo ok 1 - testvol set up

echo ${IPADDR} master | ${SSH} root@${slave} "cat >>/etc/hosts"
echo ${IPADDR2} slave | ${SSH} root@${slave} "cat >>/etc/hosts"
${SCP} ${HOME}/.ssh/known_hosts root@${slave}:${HOME}/.ssh/known_hosts
${SSH} root@${slave} hostname slave

${SSH} root@${slave} pvcreate -ff ${DEV1NAME}
${SSH} root@${slave} vgcreate testvg ${DEV1NAME}
${SSH} root@${slave} lvcreate --size 16M -n test testvg
${SSH} root@${slave} lvcreate --size 16M -n test_snap testvg

${SSH} root@${slave} zumastor define volume testvol /dev/testvg/test /dev/testvg/test_snap --initialize
${SSH} root@${slave} zumastor status --usage
echo ok 2 - slave testvol set up

zumastor define target testvol slave
${SSH} root@${slave} zumastor define source testvol master
zumastor replicate testvol --wait slave
zumastor status --usage

# reasonable wait for these small volumes to finish the initial replication
if ! timeout_remote_file_wait 120 root@${slave} /var/run/zumastor/mount/testvol
then
  $SSH root@${slave} "df -h ; mount"
  $SSH root@${slave} ls -alR /var/run/zumastor
  $SSH root@${slave} zumastor status --usage
  $SSH root@${slave} tail -200 /var/log/syslog

  echo not ok 3 - replication manually from master
  exit 3
else
  echo ok 3 - replication manually from master
fi

date >>/var/run/zumastor/mount/testvol/testfile
sync

# stop master and replication
zumastor stop target testvol slave
zumastor stop master testvol
${SSH} root@${slave} zumastor stop source testvol

# enlarge origin volume
echo y | lvresize /dev/testvg/test -L 20M
zumastor resize testvol --origin 20M
e2fsck -f -y /dev/mapper/testvol
resize2fs /dev/mapper/testvol 20M
$SSH root@${slave} "echo y | lvresize /dev/testvg/test -L 20M"
$SSH root@${slave} zumastor resize testvol --origin 20M

# restart master and replication
zumastor start master testvol
zumastor start target testvol slave
$SSH root@${slave} zumastor start source testvol

zumastor replicate testvol slave --wait
zumastor status --usage
file_check 4 "origin and slave testfiles are in sync after origin enlarging"

date >>/var/run/zumastor/mount/testvol/testfile
sync

# stop master and replication
zumastor stop target testvol slave
zumastor stop master testvol
${SSH} root@${slave} zumastor stop source testvol


# shrink origin volume
e2fsck -f -y /dev/mapper/testvol
resize2fs /dev/mapper/testvol 12M
dd if=/dev/zero of=/dev/mapper/testvol bs=1k seek=12k count=4k
sync
zumastor resize testvol --origin 12M
echo y | lvresize /dev/testvg/test -L 12M
$SSH root@${slave} zumastor resize testvol --origin 12M
$SSH root@${slave} "echo y | lvresize /dev/testvg/test -L 12M"

# restart master and replication
zumastor start master testvol
zumastor start target testvol slave
$SSH root@${slave} zumastor start source testvol

zumastor replicate testvol slave --wait
zumastor status --usage
file_check 5 "origin and slave testfiles are in sync after origin shrinking"

date >>/var/run/zumastor/mount/testvol/testfile
sync
lvresize /dev/testvg/test_snap -L 40M
zumastor resize testvol --snapshot 40M
zumastor replicate testvol slave --wait
zumastor status --usage
file_check 6 "origin and slave testfiles are in sync after snapshot enlarging"

date >>/var/run/zumastor/mount/testvol/testfile
sync
zumastor resize testvol --snapshot 12M
echo y | lvresize /dev/testvg/test_snap -L 12M
zumastor replicate testvol slave --wait
zumastor status --usage
file_check 7 "origin and slave testfiles are in sync after snapshot shrinking"

# cleanup
zumastor forget volume testvol
${SSH} root@${slave} zumastor forget volume testvol
echo "ok 8 - cleanup"

exit 0
