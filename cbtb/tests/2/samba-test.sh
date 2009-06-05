#!/bin/sh -x
#
# $Id$
#
# Export zumastor over CIFS to a slave and then perform some filesystem
# actions.  Verify that the filesystem actions arrive in the snapshot store.
#
# Copyright 2007 Google Inc.  All rights reserved
# Author: Mark Roach (mrroach@google.com)
# Original Author: Drake Diedrich (dld@google.com)


set -e

rc=0

# Terminate test in 20 minutes.  Read by test harness.
TIMEOUT=2400
NUMDEVS=2
DEV1SIZE=4
DEV2SIZE=8
#DEV1NAME=/dev/null
#DEV2NAME=/dev/null

# See test 7 below.  Found race condition in samba/smbfs deleting files.
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




echo "1..8"
echo ${IPADDR} master >>/etc/hosts
echo ${IPADDR2} slave >>/etc/hosts
hostname master
zumastor define volume testvol ${DEV1NAME} ${DEV2NAME} --initialize
mkfs.ext3 /dev/mapper/testvol
zumastor define master testvol; zumastor define schedule testvol -h 24 -d 7
ssh-keyscan -t rsa slave >>${HOME}/.ssh/known_hosts
ssh-keyscan -t rsa master >>${HOME}/.ssh/known_hosts
echo ok 1 - testvol set up

if [ -d /var/run/zumastor/mount/testvol/ ] ; then
  echo ok 2 - testvol mounted
else
  echo "not ok 2 - testvol mounted"
  exit 2
fi

sync
zumastor snapshot testvol hourly 

if timeout_file_wait 30 /var/run/zumastor/snapshot/testvol/hourly.0 ; then
  echo "ok 3 - first snapshot mounted"
else
  ls -lR /var/run/zumastor/
  echo "not ok 3 - first snapshot mounted"
  exit 3
fi


# preconfigure so not asked for samba workgroup
mkdir /etc/samba
cat > /etc/samba/smb.conf << EOF
[global]
  workgroup = ZUMABUILD
  passdb backend = tdbsam
  load printers = no
  socket options = TCP_NODELAY

[testvol]
  path=/var/run/zumastor/mount/testvol
  writable = yes
EOF

# update-inetd tries to do tricky things to /dev/tty
rm /usr/sbin/update-inetd && ln -s /bin/true /usr/sbin/update-inetd
apt-get update
DEBIAN_FRONTEND=noninteractive aptitude install -y samba

if /etc/init.d/samba restart ; then
  echo ok 4 - testvol exported
else
  echo not ok 4 - testvol exported
  exit 4
fi

# Set the samba password for the zbuild user
printf 'password\npassword\n' | smbpasswd -a -s root

echo ${IPADDR} master | ${SSH} root@${slave} "cat >>/etc/hosts"
echo ${IPADDR2} slave | ${SSH} root@${slave} "cat >>/etc/hosts"
${SCP} ${HOME}/.ssh/known_hosts root@${slave}:${HOME}/.ssh/known_hosts
${SSH} root@${slave} hostname slave
${SSH} root@${slave} apt-get update
${SSH} root@${slave} DEBIAN_FRONTEND=noninteractive aptitude install -y smbfs
${SSH} root@${slave} modprobe cifs || true
${SSH} root@${slave} mount //master/testvol /mnt -t cifs -o user=root,pass=password
${SSH} root@${slave} mount
echo ok 5 - slave set up


date >> /var/run/zumastor/mount/testvol/masterfile
hash=`md5sum </var/run/zumastor/mount/testvol/masterfile`
rhash=`${SSH} root@${slave} 'md5sum </mnt/masterfile'`
if [ "x$hash" = "x$rhash" ] ; then
  echo ok 5 - file written on master matches CIFS client view
else
  rc=5
  echo not ok 5 - file written on master matches CIFS client view
fi

date | ${SSH} root@${slave} "cat >/mnt/clientfile"
hash=`md5sum </var/run/zumastor/mount/testvol/clientfile`
rhash=`${SSH} root@${slave} 'md5sum </mnt/clientfile'`
if [ "x$hash" = "x$rhash" ] ; then
  echo ok 6 - file written on CIFS client visible on master
else
  rc=6
  echo not ok 6 - file written on CIFS client visible on master
fi

#
# This is the test that's known to fail occaisionally, depending
# on speed.  Putting something (like the SSH commented out here)
# tends to make it work.
#
rm /var/run/zumastor/mount/testvol/masterfile
#$SSH root@${slave} ls -l /mnt/ || true
attempt=0
while true
do
  attempt=$(($attempt+1))
  if [ $attempt -gt 30 ]
  then
    rc=7
    echo not ok 7 - rm on master did not show up on CIFS client
    break
  fi
  if ! $SSH root@${slave} test -f /mnt/masterfile
  then
    echo ok 7 - rm on master did show up on CIFS client
    break
  fi
done
${SSH} root@${slave} rm /mnt/clientfile
if [ -f /mnt/masterfile ] ; then
  rc=8
  echo not ok 8 - rm on CIFS client did not show up on master
else
  echo ok 8 - rm on CIFS client did show up on master
fi


exit $rc
