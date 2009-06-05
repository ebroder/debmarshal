#!/bin/sh -x
#
# $Id$
#
#
# run the cbtb test suite under multiple tunbr invocations from
# continuous-test.sh, store the results in the build/ directory, and email
# the zumastor-commits list.  Return code indicates that at least
# one mandatory rest failed, and is used by the continuous-test.sh
# loop to avoid rerunning failed tests.

top="${PWD}"
branch=`cat $top/zumastor/Version`

installrev=''
if [ -f ${top}/zumastor/build/installrev ] ; then
  installrev=`cat ${top}/zumastor/build/installrev`
fi
  
testrev=''
if [ -f ${top}/zumastor/build/testrev ] ; then
  testrev=`cat ${top}/zumastor/build/testrev`
fi
    

          
mailto=/usr/bin/mailto
sendmail=/usr/sbin/sendmail
biabam=/usr/bin/biabam
email_failure="zumastor-commits@googlegroups.com"
email_success="zumastor-commits@googlegroups.com"
repo="${top}/zumastor-tests"
export LOGDIR="${top}/zumastor/build/r$installrev"
export DISKIMG="${LOGDIR}/dapper-i386-zumastor-r$installrev.img"
[ -d $LOGDIR ] || mkdir $LOGDIR

summary=${LOGDIR}/summary
> $summary

[ -x /etc/default/testenv ] && . /etc/default/testenv




if [ ! -d ${repo} ] ; then
  echo "svn checkout http://zumastor.googlecode.com/svn/trunk/cbtb/tests zumastor-tests"
  echo "cp $0 to the parent directory of the zumastor-tests repository and "
  echo "run from that location.  Periodically inspect the cbtb/host-scripts"
  echo "for changes and redeploy them."
  exit 1
fi

pushd ${repo}

# build and test the last successfully installed revision
svn update -r $installrev

testret=0

pushd 1
for f in *.sh
do
  # timeout any test that runs for more than an hour
  export LOGPREFIX="$f."
  testlog="${LOGDIR}/${LOGPREFIX}log"
  MACADDR=$MACADDR IPADDR=$IPADDR IFACE=$IFACE \
    MACADDR2= IPADDR2= IFACE2= \
    MACADDR3= IPADDR3= IFACE3= \
    DEV1NAME=/dev/sdb DEV2NAME=/dev/sdc DEV3NAME=/dev/sdd \
    timeout -14 3600 ${top}/test-zuma-dapper-i386.sh $f >${testlog} 2>&1
  testrc=$?
  files="$testlog $files"
  if [ $testrc -eq 0 ]
  then
    echo PASS $f >>$summary
  else
    if egrep '^EXPECT_FAIL=1' ./${f} ; then
      echo FAIL "$f*" >>$summary
    else
      testret=$testrc
      echo FAIL $f >>$summary
    fi

    if [ -f "${LOGDIR}/${LOGPREFIX}screen.png" ] ; then
      files="${LOGDIR}/${LOGPREFIX}screen.png $files"
    fi

  fi
done
popd

pushd 2
for f in *.sh
do
  export LOGPREFIX="$f."
  testlog="${LOGDIR}/${LOGPREFIX}log"
  MACADDR=$MACADDR IPADDR=$IPADDR IFACE=$IFACE \
    MACADDR2=$MACADDR2 IPADDR2=$IPADDR2 IFACE2=$IFACE2 \
    MACADDR3= IPADDR3= IFACE3= \
    DEV1NAME=/dev/sdb DEV2NAME=/dev/sdc DEV3NAME=/dev/sdd \
    timeout -14 3600 ${top}/test-zuma-dapper-i386.sh $f >${testlog} 2>&1
  testrc=$?
  files="$testlog $files"
  if  [ $testrc -eq 0 ]
  then
    echo PASS $f >>$summary
  else
    if egrep '^EXPECT_FAIL=1' ./${f} ; then
      echo FAIL "$f*" >>$summary
    else
      testret=$testrc
      echo FAIL $f >>$summary
    fi

    if [ -f "${LOGDIR}/$LOGPREFIX}screen.png" ] ; then
      files="${LOGDIR}/$LOGPREFIX}screen.png $files"
    fi
    if [ -f "${LOGDIR}/$LOGPREFIX}screen2.png" ] ; then
      files="${LOGDIR}/$LOGPREFIX}screen2.png $files"
    fi

  fi
done
popd

pushd 3
for f in *.sh
do
  export LOGPREFIX="$f."
  testlog="${LOGDIR}/${LOGPREFIX}log"
  export DEV1NAME=/dev/sdb DEV2NAME=/dev/sdc DEV3NAME=/dev/sdd
  timeout -14 3600 ${top}/test-zuma-dapper-i386.sh $f >${testlog} 2>&1
  testrc=$?
  files="$testlog $files"
  if  [ $testrc -eq 0 ]
  then
    echo PASS $f >>$summary
  else
    if egrep '^EXPECT_FAIL=1' ./${f} ; then
      echo FAIL "$f*" >>$summary
    else
      testret=$testrc
      echo FAIL $f >>$summary
    fi

    if [ -f "${LOGDIR}/$LOGPREFIX}screen.png" ] ; then
      files="${LOGDIR}/$LOGPREFIX}screen.png $files"
    fi
    if [ -f "${LOGDIR}/$LOGPREFIX}screen2.png" ] ; then
      files="${LOGDIR}/$LOGPREFIX}screen2.png $files"
    fi
    if [ -f "${LOGDIR}/$LOGPREFIX}screen3.png" ] ; then
      files="${LOGDIR}/$LOGPREFIX}screen3.png $files"
    fi

  fi
done
popd

popd
    
# send summary, logs, and a success or failure subject to the
# success or failure mailing lists
if [ $testret -eq 0 ]; then
  subject="zumastor b$branch r$installrev test success"
  email="${email_success}"

  # update the presistent revision number of the last revision that passed
  # all required tests
  echo $installrev >${top}/zumastor/build/testrev.new
  mv ${top}/zumastor/build/testrev.new ${top}/zumastor/build/testrev

else
  subject="zumastor b$branch r$installrev test failure $testret"
  email="${email_failure}"
fi


# send $subject and $files to $email
if [ -x ${mailto} ] ; then
  (
    cat $summary
    for f in $files
    do
      echo '~*'
      echo 1
      echo $f
      echo text/plain
    done
  ) | ${mailto} -s "${subject}" ${email}

elif [ -x ${biabam} ] ; then
  bfiles=`echo $files | tr ' ' ','`
  cat $summary | ${biabam} $bfiles -s "${subject}" ${email}

elif [ -x ${sendmail} ] ; then
  (
    echo "Subject: " $subject
    echo
    cat $summary
    for f in $files
    do
      echo
      echo $f
      echo "------------------"
      cat $f
    done
  ) | ${sendmail} ${email}
fi

exit $testret
