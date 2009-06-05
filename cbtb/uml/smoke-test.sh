#!/bin/bash

# $Id: smoke.sh 1198 2007-12-22 11:43:15Z drake.diedrich $
#
# build-i386.sh requires root privs via sudo, so this smoke test may
# only be run interactively and is inherently somewhat dangerous.
# You should inspect the scripts before running them.
#
# Several portions of this script require your host have some of the cbtb
# setup scripts.  See cbtb/host-setup/README, and in particular
# interfaces-bridge.sh, proxy.sh, and dnsmasq.sh.
#
#

set -e

if [ "x$LINENO" = "x" ]
then
  echo "Looks like you are not using bash"
  echo "Please re-run with bash"
  exit 1
fi

ARCH=`dpkg --print-architecture`

[ -f /etc/lsb-release ] && . /etc/lsb-release

pick_dist_ver() {
  if [ "x$DISTRIB_CODENAME" = "xhardy" ] || [ "x$DISTRIB_CODENAME" = "xintrepid" ]
  then
    echo "hardy"
    return 0
  else
    echo "etch"
    return 0
  fi
}

pick_dist() {
  if [ "x$DISTRIB_CODENAME" = "xhardy" ] || [ "x$DISTRIB_CODENAME" = "xintrepid" ]
  then
    echo "ubuntu"
    return 0
  else
    echo "debian"
    return 0
  fi
}

if [ "x$DIST" = "x" ]
then
  DIST=`pick_dist_ver`
fi

if [ "x$LINUXDISTRIBUTION" = "x" ]
then
  LINUXDISTRIBUTION=`pick_dist`
fi

echo "Starting to smoke-test zumastor"
echo "Using $LINUXDISTRIBUTION $DIST for $ARCH"
echo "If you wish to test another combination, you may pass environment vars"
echo "or you may need to change your host arch."

envstring="env DIST=$DIST ARCH=$ARCH LINUXDISTRIBUTION=$LINUXDISTRIBUTION"

time $envstring ./setup.sh
time $envstring ./build.sh
time $envstring ./runtests.sh $*
