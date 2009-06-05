#!/bin/bash

# $Id$
#
# Tests run without privileges, other than those granted by tunbr, which
# must be installed first, along with interfaces-bridge.sh, proxy.sh, and
# dnsmasq.sh as described in cbtb/host-setup/README.
# Defaults to testing on dapper/i386 installed template images, DIST=etch
# and ARCH=i386 may also currently be specified.
#

set -e

smoketests1="snapshot-zumastor-xfs-2045G.sh"
smoketests2="replication-zumastor.sh"
nofail=0
all=0

if [ "x$ARCH" = "x" ] ; then
  ARCH=`dpkg --print-architecture || echo i386`
fi

if [ "x$DIST" = "x" ] ; then
  DIST=etch
fi

usage() {
  cat <<EOF
$0 [--all] [--no-fail]

--all   Run all tests in cbtb/tests/1/ and cbtb/tests/2/, rather than just
        the smoketests: $smoketests1 $smoketests2.
--no-fail  Do not try and run failing tests

Environment variables:
ARCH - the CPU/ABI architecture to test.     currently: $ARCH
DIST - the distribution release to test on.  currently: $DIST
EOF
}

testparent=../tests

while true
do
  case $1 in
    --all)
      all=1
      shift
      ;;

   --no-fail)
      nofail=1
      shift
      ;;

   --help|-h)
     usage
     exit 1
     ;;

   --)
     shift
     break
     ;;

   *)
     echo "$1 is unknown"
     #echo "Internal error"
     break
     ;;
   esac
done

summary=`mktemp`

if [ $all -eq 1 ]
then
  echo "INFO: Running all tests"
  tests1=`cd $testparent/1 && echo *.sh`
  tests2=`cd $testparent/2 && echo *.sh`
  tests3=`cd $testparent/3 && echo *.sh`
else
  tests1=$smoketests1
  tests2=$smoketests2
fi

[ $nofail -eq 1 ] && echo "INFO: Skipping EXPECT_FAIL tests"

skip_test() {
  testname=$1
  egrep -q EXPECT_FAIL=1 $testname && [ $nofail -eq 1 ]
  return $?
}

for test in $tests1
do
  if skip_test $testparent/1/$test
  then
    echo SKIP $test >> $summary
    continue
  fi
  if DIST=$DIST ARCH=$ARCH time tunbr ./test-zuma-uml.sh $testparent/1/$test
  then
    echo PASS $test >>$summary
  else
    echo FAIL $test >>$summary
  fi
done

for test in $tests2
do
  if skip_test $testparent/2/$test
  then
    echo SKIP $test >> $summary
    continue
  fi
  if  DIST=$DIST ARCH=$ARCH time tunbr tunbr ./test-zuma-uml.sh $testparent/2/$test
  then
    echo PASS $test >>$summary
  else
    echo FAIL $test >>$summary
  fi
done

for test in $tests3
do
  if skip_test $testparent/3/$test
  then
    echo SKIP $test >> $summary
    continue
  fi
  if  DIST=$DIST ARCH=$ARCH time tunbr tunbr tunbr ./test-zuma-uml.sh $testparent/3/$test
  then
    echo PASS $test >>$summary
  else
    echo FAIL $test >>$summary
  fi
done

echo
cat $summary
rm -f $summary

# Kill any testers still hanging around
pgrep test-zuma-uml|xargs kill -9
