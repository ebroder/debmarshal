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

in-target apt-get dist-upgrade -y

apt-install openssh-server cron dmsetup build-essential \
  lockfile-progs debconf libterm-readline-gnu-perl

in-target apt-get clean

cat <<EOF >> /target/etc/network/interfaces

# also try to bring up eth1 due to qemu emulation quirk
allow-hotplug eth1
iface eth1 inet dhcp
EOF

# set noapic on the grub kernel boot stanza
in-target sed --in-place '/^kernel/s/$/ noapic/' /boot/grub/menu.lst
