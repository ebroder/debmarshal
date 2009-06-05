#!/bin/sh -x
#
# $Id$
#
#
# Continuously svn update, run the encapsulated build
# Create symlinks to the new debs each time a new build is successful,
# so other continuous-* scripts can tell at a glance that a new one
# has arrived.

mailto=/usr/bin/mailto
sendmail=/usr/sbin/sendmail
biabam=/usr/bin/biabam
TUNBR=tunbr
email_failure="zumastor-commits@googlegroups.com"
email_success="zumastor-commits@googlegroups.com"
repo="${PWD}/zumastor"
top="${PWD}"

# obtain a lock on the repository to build, and a general build lock so
# only one build runs at once
repolock=${repo}/lock
if [ "x$LOCKFILE" = "x" ] ; then
  locks="$repolock"
else
  locks="$LOCKFILE $repolock"
fi
lockfile $locks


branch=`cat $repo/Version`

[ -x /etc/default/testenv ] && . /etc/default/testenv


if [ ! -f zumastor/Changelog ] ; then
  echo "cp $0 to the parent directory of the zumastor repository and "
  echo "run from that location.  Periodically inspect the three "
  echo "host scripts for changes and redeploy them."
  exit 1
fi

oldrevision=
if [ -f ${top}/zumastor/build/buildrev ]
then
  read oldrevision <${top}/zumastor/build/buildrev
fi


pushd ${repo}

# build and test the current working directory packages
revision=`svn info | awk '/Revision:/ { print $2; }'`
buildlog="build/r${revision}/build-r${revision}.log"
buildret=-1

if [ ! -d "build/r${revision}" ] ; then
  mkdir "build/r${revision}"
fi

# set flags for the parts of the build that are unnecessary.  Currently
# only check for kernel diffs
echo -n "Rebuilding the kernel between $oldrevision and $revision "
nobuild=
if [ "x$oldrevision" != "x" ]
then
  nobuild="--no-kernel "
  for kernel_dirs in kernel zumastor/patches ddsnap/patches ddsnap/kernel; do
    pushd $kernel_dirs
    if [ `svn diff -r$oldrevision | wc -c` -ne 0 ]
    then
      nobuild=
      popd
      break
    fi
    popd
  done
  if [ `svn diff -r$oldrevision KernelVersion | wc -c` -ne 0 ]
  then
    nobuild=
  fi
fi


# give dapper-build one more hour than its internal timeout
time ${TUNBR} timeout -14 176400 ${top}/dapper-build.sh $nobuild >${buildlog} 2>&1
buildret=$?
echo continuous dapper-build returned $buildret



if [ $buildret -eq 0 ]; then
  subject="zumastor b$branch r$revision build success"
  files="$buildlog"
  email="${email_success}"
  # store the revision just built in build/buildrev
  # in the installer stage running in a separate loop
  echo $revision >${top}/zumastor/build/buildrev.new
  mv ${top}/zumastor/build/buildrev.new ${top}/zumastor/build/buildrev
else
  subject="zumastor b$branch r$revision build failure $buildret"
  files="$buildlog"
  email="${email_failure}"
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
    echo "Subject: " $subject
    echo
    for f in $files
    do
      cat $f
    done
  ) | ${sendmail} ${email}
fi

# remove locks, just waiting now for another update
rm -f $locks


# loop waiting for a new update
oldrevision=${revision}
diff=`mktemp`
while true
do

  # get just the repository lock for the update
  lockfile $repolock

  svn update
  revision=`svnversion || svn info | awk '/Revision:/ { print $2; }'`

  # the diff between the old revision and the current one
  svn diff -r$oldrevision >$diff

  # free lock
  rm -f $repolock

  # wait and loop if the revision number is the same
  if [ "x$revision" = "x$oldrevision" ]
  then
    sleep 300

  # wait and loop if the diff is zero length
  elif [ ! -s "$diff" ]
  then
    sleep 300

  else
    # restart continuous.sh, beginning a new build
    popd
    exec $0
  fi
done
