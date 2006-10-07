#!/bin/bash

# Copyright 2006 Google Inc. All Rights Reserved.
# Time-stamp: <2006-09-14 15:40:27 cklin>

DEBMARSHAL=/usr/lib/debmarshal

if [ "$#" -ne 1 ] ; then
    cat << EOF

Debmarshal Database Reload Script
Chuan-kai Lin <cklin@google.com>
================================

This script reconstructs the Debmarshal Berkeley DB tables using only
a package pool and an existing dists/ directory tree created by
Debmarshal.  Since it does not consult the Berkeley DB tables in the
original repository, you can use the script to migrate to a new
database schema or to fix corrupted databases.


Limitations
-----------

The new repository will differ from the old one in various ways
because it is not possible (or not easy) to reconstruct all metadata
without looking into the Berkeley DB tables of the old repository.

* snapshot track: the new repository will contain only one release in
  the snapshot track regardless of how many there were in the old one.

* release numbering: releases in each new track will be renumbered
  with serial numbers starting from 0.  For example, if you removed
  the dists/ subtrees for release 0-7 and 9, the old release 8 will
  become release 0, and the old release 10 will become release 1, etc.

* aliases: the new tracks will contain only the auto-generated
  'latest' alias.  All other aliases in old tracks are lost.

* latest: the latest alias will have timestamps corresponding to the
  execution of the reload script.  The information on when each
  release were created in the old repository is lost.

* pool: the reload script does not trim, or in any other way modify,
  the contents of the pool hierarchy.


Script Usage
------------

Before invoking the script, you need the following preparations.  The
old repository must contain a dists/ directory tree that follows the
Debmarshal-standard dists/track/release/component/arch structure.  The
new repository must contain a Debmarshal configuration file in config/
and all the needed packages in the pool/ directory tree.  Make sure
that config/repository has Mode set to "tracking" , not "supervised".
Then, invoke the following command in the root of the new repository:

  $0 path_to_old_repository

EOF
    exit 1
fi

FROM=$1
ERROR=0

if [ ! -d "${FROM}" ] ; then
    echo "The path '${FROM}' does not refer to a directory"
elif [ ! -d "${FROM}/dists" ] ; then
    echo "Repository '${FROM}' does not contain a dists/ subdirectory"
elif [ ! -f "config/repository" ] ; then
    echo "Current directory does not contain a config/repository file"
elif [ ! -d "pool" ] ; then
    echo "Current directory does not contain a pool/ subdirectory"
elif [ -d "dists" ] ; then
    echo "Current directory already contains a dists/ subdirectory"
elif [ -d "dbs" ] ; then
    echo "Current directory already contains a dbs/ subdirectory"
else
    ERROR=1
fi
[ $ERROR ] && exit 1

mkdir dbs

echo "Indexing contents of the pool ..."
${DEBMARSHAL}/index_pool.py
echo

for TRACK in ${FROM}/dists/* ; do
    [ "${TRACK}" = "${FROM}/dists/snapshot" ] && continue
    [ -L "${TRACK}" ] && continue
    [ -d "${TRACK}" ] || continue

    BASE=`basename ${TRACK}`
    grep -q "^\[${BASE}\]" config/repository
    if [ "$?" != "0" ] ; then
	echo "Track ${BASE} is not configured in config/repository"
	continue
    fi

    echo "Processing track ${TRACK} ..."

    TMPFILE=`mktemp` || exit 2
    for RELEASE in ${TRACK}/* ; do
	[ -L "${RELEASE}" ] && continue
	[ -d "${RELEASE}" ] || continue
	echo `basename ${RELEASE}` >> $TMPFILE
    done

    for RELEASE in `grep -E "^[0-9]+" $TMPFILE | sort -n` ; do
	echo "Processing release ${RELEASE} ..."
	${DEBMARSHAL}/make_release.py -t ${BASE} -d ${TRACK}/${RELEASE} commit
	NEW_RELEASE=`readlink dists/${BASE}/latest`
	echo "Release ${BASE}/${RELEASE} becomes ${BASE}/${NEW_RELEASE}"
	echo
    done
    echo

    rm -f ${TMPFILE}
done

