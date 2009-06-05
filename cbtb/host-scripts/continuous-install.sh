#!/bin/sh -x
#
# $Id$
#

# Continuously check whether a new build has completed, and install
# the new debs into a new image to use for testing.  Create a symlink to
# the new image for the continuous-test script to notice and launch tests
# against.

repo="${PWD}/zumastor"
top="${PWD}"
branch=`cat $repo/Version`

buildrev=''
if [ -f ${repo}/build/buildrev ] ; then
  buildrev=`cat ${repo}/build/buildrev`
fi

installrev=''
if [ -f ${repo}/build/installrev ] ; then
  installrev=`cat ${repo}/build/installrev`
fi

if [ "x$buildrev" = "x$installrev" ] ; then
  # wait 5 minutes and restart the script.  Don't do anything until
  # the symlinks to the revision numbers are actually different
  # restarting allows for easily deploying changes to this script.
  sleep 300
  exec $0
fi

if [ "x$FAILED_INSTALL_REV" = "x$buildrev" ] ; then
  # if the last install failed, FAILED_INSTALL_REV was exported
  # before this script was rerun, and if installrev still points to the
  # same revision number, continue waiting rather than trying to restart.
  # Intervention (such as a build-system reboot) is required to re-test
  # the same version.
  sleep 300
  exec $0
fi
              
mailto=/usr/bin/mailto
sendmail=/usr/sbin/sendmail
biabam=/usr/bin/biabam
TUNBR=tunbr
email_failure="zumastor-commits@googlegroups.com"
email_success="zumastor-commits@googlegroups.com"
repo="${top}/zumastor"

diskimgdir=${HOME}/testenv
[ -x /etc/default/testenv ] && . /etc/default/testenv

export BUILDDIR="${top}/zumastor/build"
export SVNREV=$buildrev
export TEMPLATEIMG="${BUILDDIR}/dapper-i386.img"
export DISKIMG="${BUILDDIR}/r${SVNREV}/dapper-i386-zumastor-r${SVNREV}.img"


pushd ${BUILDDIR}

if [ ! -d r${SVNREV} ] ; then
  mkdir r${SVNREV}
fi

# dereference template symlink so multiple templates may coexist
if [ -L "${TEMPLATEIMG}" ] ; then
  TEMPLATEIMG=`readlink "${TEMPLATEIMG}"`
fi

export LOGDIR="${BUILDDIR}/r${buildrev}"
# build and test the current working directory packages
installlog=$LOGDIR/install-r${buildrev}.log
installret=-1

rm -f ${diskimg}
time ${TUNBR} \
  timeout -14 7200 \
  ${HOME}/zuma-dapper-i386.sh >${installlog} 2>&1
installret=$?
echo continuous zuma-dapper-i386 returned $installret

popd

if [ $installret -eq 0 ]; then
  subject="zumastor b$branch r$buildrev install success"
  files="$installlog"
  email="${email_success}"

  # update the revision number that last successfully installed
  echo $buildrev >${repo}/build/installrev.new
  mv ${repo}/build/installrev.new ${repo}/build/installrev
  export FAILED_INSTALL_REV=
  
else
  subject="zumastor b$branch r$buildrev install failure $installret"
  files="$installlog"
  email="${email_failure}"
  export FAILED_INSTALL_REV=$buildrev
fi


# send $subject and $files to $email
if [ -x ${mailto} ] ; then
  (
    for f in $files
    do
      echo '~*'
      echo 1
      echo $f
      echo text/plain
    done
  ) | ${mailto} -s "${subject}" ${email}

elif [ -x ${biabam} ] ; then
  bfiles=""
  totallength=`wc -l $files|tail -n 1|awk '{print $1}'`
  maxlength=100
  tmpfile=`mktemp`
  for f in $files
  do
    gzip -c $f > $f.gz
    if [ "x$bfiles" = "x" ]
    then
      bfiles="$f.gz"
    else
      bfiles="$bfiles,$f.gz"
    fi
  done
  if [ $totallength -gt $maxlength ]
  then
    cat $files | head -n $maxlength >> $tmpfile
    echo "-- Message truncated at ${maxlength} lines --" >> $tmpfile
  else
    cat $files >> $tmpfile
  fi
  cat $tmpfile | ${biabam} $bfiles -s "${subject}" ${email}
  rm $tmpfile
elif [ -x ${sendmail} ] ; then
  (
    echo "Subject: $subject"
    echo
    for f in $files
    do
      cat $f
    done
  ) | ${sendmail} ${email}
fi

# pause 5 minutes, then restart and try again if there has been an update
sleep 300
exec $0
