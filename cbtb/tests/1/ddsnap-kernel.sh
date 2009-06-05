#!/bin/sh -x
#
# $Id$
#
# Make sure we can load the ddsnap kernel module
#
# Copyright 2007 Google Inc.  All rights reserved
# Author: Will Nowak (willn@google.com)


set -e

TIMEOUT=1200
NUMDEVS=0

echo "1..4"

depmod -a
echo 'ok 1 - depmod'

# Try to load the kernel module, but don't fail if it isn't there.
# ddsnap could be compiled into the kernel.
modprobe dm-ddsnap || true
echo 'ok 2 - modprobe'

if [ -f /proc/kallsyms ]
then
  echo 'ok 3 - /proc/kallsyms exists'
else
  echo 'not ok 3 - no /proc/kallsyms'
  exit 3
fi

if grep -q dm_ddsnap /proc/kallsyms
then
  echo 'ok 4 - ddsnap found in /proc/kallsyms'
else
  echo 'not ok 4 - ddsnap not found in /proc/kallsyms'
  exit 4
fi
