#!/bin/sh -x

# $Id$

# simple paramter script for zuma-test-dapper-i386.sh script
# will wait until return is pressed

set -e

env
hostname
ifconfig eth0 || true
ifconfig eth1 || true

echo "slogin root@ the IP address above to work interactively"
echo "Press return to end the session"

read ret
