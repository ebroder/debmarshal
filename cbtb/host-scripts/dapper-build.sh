#!/bin/sh -x
#
# $Id$
#
# Launch a dapper-i386 snapshot
# create a build user in the snapshot
# copy the zumastor source to ~build
# run buildcurrent.sh as user build in the testenv instance
# pull the debs out of the instance
# shut down the instance
#
# Copy this to a directory outside the working directory, and launch
# with the top level of the working directory
#
# Copyright 2007 Google Inc.
# Author: Drake Diedrich <dld@google.com>
# License: GPLv2

set -e

buildflags=
buildkernel="true"
while [ $# -ge 1 ]
do
  case $1 in
    --no-kernel)
        buildflags="$buildflags --no-kernel"
        buildkernel=false
        ;;
  esac
  shift
done

rc=0

KERNEL_VERSION=`awk '/^2\.6\.[0-9]+(\.[0-9]+)?$/ { print $1; }' KernelVersion`
if [ "x$KERNEL_VERSION" = "x" ] ; then
  echo "Suspect KernelVersion file"
  exit 64
fi
VERSION=`awk '/[0-9]+\.[0-9]+(\.[0-9]+)?$/ { print $1; }' Version`
if [ "x$VERSION" = "x" ] ; then
  echo "Suspect Version file"
  exit 65
fi
SVNREV=`awk '/^[0-9]+$/ { print $1; }' SVNREV || svnversion | tr [A-Z] [a-z] || svn info zumastor | grep ^Revision:  | cut -d\  -f2`
ARCH=i386


if [ "x$MACFILE" = "x" -o "x$MACADDR" = "x" -o "x$IFACE" = "x" ] ; then
  echo "Run this script under tunbr"
  exit 66
fi

SSH='ssh -o StrictHostKeyChecking=no'
SCP='timeout -14 3600 scp -o StrictHostKeyChecking=no'
CMDTIMEOUT='time timeout -14 300'
BUILDTIMEOUT='time timeout -14 172800'
SETUPTIMEOUT='time timeout -14 3600'
WGETTIMEOUT='time timeout -14 3600'


# defaults, overridden by /etc/default/testenv if it exists
# diskimgdir should be local for reasonable performance
size=10G
tftpdir=/tftpboot
rqemu_i386=qemu  # could be kvm, kqemu version, etc.  Must be 0.9.0 to net boot.
qemu_threads=1

[ -x /etc/default/testenv ] && . /etc/default/testenv

threads=$(($qemu_threads + 1))
mem=$(($threads * 128 + 768))


tmpdir=`mktemp -d /tmp/${IMAGE}.XXXXXX`
SERIAL=${tmpdir}/serial
MONITOR=${tmpdir}/monitor
VNC=${tmpdir}/vnc

diskimg=build/`readlink build/dapper-i386.img`

if [ ! -f ${diskimg} ] ; then
  echo "No $diskimg available.  Run dapper-i386.sh first."
  exit 67
fi

echo IPADDR=${IPADDR}
echo control/tmp dir=${tmpdir}

${rqemu_i386} -snapshot -m ${mem} -smp ${qemu_threads} \
  -serial unix:${SERIAL},server,nowait \
  -monitor unix:${MONITOR},server,nowait \
  -vnc unix:${VNC} \
  -net nic,macaddr=${MACADDR} -net tap,ifname=${IFACE},script=no \
  -boot c -hda ${diskimg} -no-reboot & qemu=$!

# kill the emulator if any abort-like signal is received
trap "kill -9 ${qemu} ; exit 68" 1 2 3 6 14 15

while ! ${SSH} root@${IPADDR} hostname >/dev/null 2>&1
do
  echo -n .
  sleep 10
done

if [ ! -d build ] ; then
  mkdir build
fi

pushd build
if [ ! -f linux-${KERNEL_VERSION}.tar.bz2 ] ; then
  ${WGETTIMEOUT} wget -c http://www.kernel.org/pub/linux/kernel/v2.6/linux-${KERNEL_VERSION}.tar.bz2
fi
popd

${SETUPTIMEOUT} ${SSH} root@${IPADDR} <<EOF
lvcreate --name swap --size 5G sysvg
mkswap /dev/sysvg/swap
swapon /dev/sysvg/swap
mount -t tmpfs -o size=4G tmpfs /home
useradd build
mkdir -p ~build/.ssh ~build/zumastor/build
cp ~/.ssh/authorized_keys ~build/.ssh/
chown -R build ~build
EOF

tar cf - --exclude build --exclude .svn * | \
  ${SETUPTIMEOUT} ${SSH} build@${IPADDR} tar xf - -C zumastor
${SCP} build/linux-${KERNEL_VERSION}.tar.bz2 build@${IPADDR}:zumastor/build/

${SETUPTIMEOUT} ${SSH} root@${IPADDR} <<EOF 
cd ~build/zumastor
./builddepends.sh
echo CONCURRENCY_LEVEL := ${threads} >> /etc/kernel-pkg.conf
EOF

# replace bash with dash in the build environment, to see where it fails
# and prevent future undeclared bashisms
${SETUPTIMEOUT} ${SSH} root@${IPADDR} \
'apt-get update && aptitude install -y dash && update-alternatives --install /bin/sh sh /bin/dash 1'

# Specific kernel configurations take priority over general configurations
# kernel/config/${KERNEL_VERSION}-${ARCH} is not in the archive and may
# be a symlink to specify a specific kernel config in the local repository
# (eg. qemu-only build)
for kconf in \
  kernel/config/full \
  kernel/config/qemu \
  kernel/config/default \
  kernel/config/${KERNEL_VERSION}-${ARCH}-qemu \
  kernel/config/${KERNEL_VERSION}-${ARCH}-full \
  kernel/config/${KERNEL_VERSION}-${ARCH}
do
  if [ -e ${kconf} ] ; then
    KERNEL_CONFIG=${kconf}
  fi
done

time ${CMDTIMEOUT} \
  ${SSH} build@${IPADDR} "echo $SVNREV >zumastor/REVISION" || rc=$?

# give the build several hours, then kill it.
time ${BUILDTIMEOUT} \
  ${SSH} build@${IPADDR} "cd zumastor && ./buildcurrent.sh $buildflags $KERNEL_CONFIG" || \
  rc=$?

BUILDSRC="build@${IPADDR}:zumastor/build/r${SVNREV}"
DEBVERS="${VERSION}-r${SVNREV}"
KVERS="${KERNEL_VERSION}-zumastor-r${SVNREV}_1.0"

files="${BUILDSRC}/ddsnap_${DEBVERS}_${ARCH}.changes \
    ${BUILDSRC}/ddsnap_${DEBVERS}_${ARCH}.deb \
    ${BUILDSRC}/ddsnap_${DEBVERS}.dsc \
    ${BUILDSRC}/ddsnap_${DEBVERS}.tar.gz \
    ${BUILDSRC}/zumastor_${DEBVERS}_${ARCH}.changes \
    ${BUILDSRC}/zumastor_${DEBVERS}_all.deb \
    ${BUILDSRC}/zumastor_${DEBVERS}.dsc \
    ${BUILDSRC}/zumastor_${DEBVERS}.tar.gz"

if [ "$buildkernel" = "true" ]
then
  files="$files \
    ${BUILDSRC}/kernel-headers-${KVERS}_${ARCH}.deb \
    ${BUILDSRC}/kernel-image-${KVERS}_${ARCH}.deb"
fi

for f in $files
do
  time ${SCP} $f build/r${SVNREV} || rc=$?
done

# create symlinks to latest build debs if rc is still 0 (good)
if [ $rc -eq 0 ] ; then
  pushd build
  ln -sf r${SVNREV}/ddsnap_${DEBVERS}_${ARCH}.deb ddsnap_build_${ARCH}.deb
  ln -sf r${SVNREV}/zumastor_${DEBVERS}_all.deb zumastor_build_all.deb
  if [ "$buildkernel" = "true" ]
  then
    ln -sf r${SVNREV}/kernel-headers-${KVERS}_${ARCH}.deb kernel-headers-build_${ARCH}.deb
    ln -sf r${SVNREV}/kernel-image-${KVERS}_${ARCH}.deb kernel-image-build_${ARCH}.deb
  fi
  popd
fi

# tell the instance to start shutting itself off.  This sometimes eventually
# results in the qemu process exitting.  Kill some other way if poweroff fails.
${CMDTIMEOUT} ${SSH} root@${IPADDR} poweroff || true

# tell the qemu instance to quit directly.  This should always work, and clean
# up sockets, and be quicker, but if it doesn't the above should also cause
# a cleanup
socat unix:${MONITOR} - <<EOF
quit
EOF

# eventually put a timeout in front of this.  timeout the command won't work
# since wait is a builtin
time wait $qemu || rc=$?

# if somehow qemu is still running, kill -9 it.  This can happen, especially
# with acceleration modules in use.
kill -0 $qemu && kill -9 $qemu

rm -rf ${tmpdir}

exit ${rc}
