#!/bin/sh

# run after the base packages are installed, from inside the d-i environment
# copied into the initrd so it doesn't need to be fetched over network
# connections.

# $Id$
# Copyright 2007 Google Inc.
# Author: Drake Diedrich <dld@google.com>
# License: GPLv2

set -e

mkdir /target/root/.ssh
cp /authorized_keys /target/root/.ssh

apt-install openssh-server cron postfix dmsetup build-essential lvm2 \
  debconf-utils debhelper devscripts fakeroot file gettext html2text \
  intltool-debian kernel-package libapr0 libexpat1 libmagic1 libneon25 \
  libpopt-dev libsvn0 libxml2 po-debconf rsync subversion zlib1g-dev \
  dash \
  insserv libevent1 libnfsidmap1 nfs-common nfs-kernel-server portmap \
  e2fsprogs jfsutils reiserfsprogs xfsprogs 
  
in-target apt-get dist-upgrade -y

in-target apt-get clean

# Since the MAC will change on subsequent copies, get rid of persistence
rm /target/etc/iftab

# set noapic and noacpi on all grub kernel boot stanzas - qemu doesn't like
# kvm likes it less, commented out again but left for further reinstatements
# in-target sed --in-place '/^# kopt=/s/$/ noapic noacpi/' /boot/grub/menu.lst
# in-target update-grub

# bring back the VC consoles
sed -i 's/^#1:/1:/' /etc/inittab
sed -i 's/^#2:/2:/' /etc/inittab
sed -i 's/^#3:/3:/' /etc/inittab
sed -i 's/^#4:/4:/' /etc/inittab
sed -i 's/^#5:/5:/' /etc/inittab
sed -i 's/^#6:/6:/' /etc/inittab

# redirect logging to VC1, so an image can be taken if necessary
echo "*.*	/dev/tty1" >> /etc/syslog.conf

