#!/bin/sh -x
#
# $Id$
#
#
# continuously run an svn update on a zumastor repository with the cbtb/tests
# Whenever the last successful test revision differs from the last successful
# install revision, fire off a new round of tests.

top="${PWD}"

installrev=''
if [ -f ${top}/zumastor/build/installrev ] ; then
  installrev=`cat ${top}/zumastor/build/installrev`
fi
  
testrev=''
if [ -f ${top}/zumastor/build/testrev ] ; then
  testrev=`cat ${top}/zumastor/build/testrev`
fi
    
if [ "x$installrev" = "x$testrev" ] ; then
  # wait 5 minutes and restart the script.  Don't do anything until
  # the symlinks to the revision numbers are actually different
  # restarting allows for easily deploying changes to this script.
  sleep 300
  exec $0
fi

if [ "x$FAILED_TEST_REV" = "x$installrev" ] ; then
  # if the last install test failed, FAILED_TEST_REV was exported
  # before this script was rerun, and if installrev still points to the
  # same revision number, continue waiting rather than trying to restart.
  # Intervention (such as a build-system reboot) is required to re-test
  # the same version.
  sleep 300
  exec $0
fi
          
          
TUNBR=tunbr
repo="${top}/zumastor-tests"

[ -x /etc/default/testenv ] && . /etc/default/testenv

if $TUNBR $TUNBR $TUNBR ./runtests.sh
then
  export FAILED_TEST_REV=
else
  export FAILED_TEST_REV=$installrev
fi

# Perhaps shorten this if a test ran successfully, as that caused
# a delay already on it's own.  
sleep 300

exec $0
