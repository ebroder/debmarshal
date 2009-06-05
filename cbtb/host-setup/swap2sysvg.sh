#!/bin/sh

# Turn the swap partition into a physical volume in the sysvg volume group

# $Id$
# Copyright 2007 Google Inc.
# Author: Drake Diedrich <dld@google.com>
# License: GPLv2

set -e

modprobe dm-mod || true
if egrep dm_mod /proc/modules ; then
  dev=`awk '/swap/ { print $1; }' /etc/fstab`
  egrep dm-mod /etc/modules || echo dm-mod >> /etc/modules
  wdev=`echo $dev | sed 's/^\([/a-z]*\)\([0-9]\)*$/\1/'`
  ndev=`echo $dev | sed 's/^\([/a-z]*\)\([0-9]\)*$/\2/'`
  if [ "x$dev" != "x/dev/mapper/swap" -a "x$ndev" != "x" ] ; then
    if [ "x`sfdisk $wdev -c $ndev`" = "x82" ] ; then
      swapoff -a || true
      sfdisk $wdev -c $ndev "8e"
      pvcreate -ff $dev
      vgcreate sysvg $dev
    fi
  fi
fi
