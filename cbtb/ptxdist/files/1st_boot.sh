#!/bin/bash
pvcreate -ff /dev/hda2
vgcreate sysvg /dev/hda2
chmod g-w /home
rm /home/1st_boot.sh
