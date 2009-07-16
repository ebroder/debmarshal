#!/usr/bin/python2.4
#
# Copyright 2006 Google Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.

"""Berkeley DB access utility functions

The bsddb_utils module contains utility functions for accessing the
Berkeley DB database tables that hold the status of the repository and
the packages contained therein.
"""

__author__ = 'cklin@google.com (Chuan-Kai Lin)'

import bsddb
import fileinput
import logging as lg
import os
import sys
import time
import urllib2
import alias_utils as au
import logging_utils as lu
import os_utils as ou


_CACHE_SIZE = 33554432


_DB_NAMES = { 'pkg_info': 'dbs/pkg_info.db',
              'src_info': 'dbs/src_info.db',
              'pkg_deps': 'dbs/pkg_deps.db',
              'file_pkg': 'dbs/file_pkg.db',
              'pool_pkg': 'dbs/pool_pkg.db',
              'releases': 'dbs/releases.db',
              'aliases':  'dbs/aliases.db' }


def RunWithDB(names, func, arg=None):
  """Invokes a function with database dictionaries

  This function provides another function func(arg, dbs) with readily
  usable Berkeley DB database dictionaries and takes care to close the
  databases after the function terminates.  The database tables to be
  opened are specified by a list of keys to the _DB_NAMES dictionary
  (or None, which means open all tables), and the opened database
  dictionaries are stored in the dbs dictionary with the same keys.
  """

  dbs = {}
  if names is None:
    names = _DB_NAMES.keys()
  for name in names:
    if name not in _DB_NAMES:
      lg.error('The ' + name + ' database does not exist')
      sys.exit()
    dbs[name] = bsddb.btopen(
      _DB_NAMES[name], 'c', cachesize=_CACHE_SIZE)
  try:
    return func(arg, dbs)
  finally:
    for db in dbs:  dbs[db].close()


def AppendEntry(db, key, value):
  """Append a value in a dictionary with ', '-separated values

  This function appends the given string into the ', '-separated value
  of the given key.  It checks if the value is already in the list and
  appends only if the search turns up negative.
  """

  if key in db:
    existing = db[key]
    if existing == value:
      return
    if existing.startswith(value + ', '):
      return
    if existing.endswith(', ' + value):
      return
    if existing.find(', ' + value + ', ') >= 0:
      return
    db[key] = existing + ', ' + value
  else:
    db[key] = value


def FindKeyStartingWith(string, db):
  """Test if there is a key with a certain initial

  This function tests if there is an entry in the database whose key
  starts with the given string.  Using the seek ability of BTree
  tables, this function works much more efficiently than enumerating
  through all entries in the table.
  """

  try:
    key = db.set_location(string)[0]
    if key.startswith(string):
      return True
    return False
  except KeyError:
    return False


def _FetchRemoteTable(base_url, db_keys):
  """Fetch Berkeley DB tables from a remote repository

  This function fetches the specified Berkeley DB tables from the
  underlying releases through an URL and save them in the dbs/
  directory.  If something goes wrong, it raises EnvironmentError.
  """

  if not os.path.isdir('dbs'):
    os.mkdir('dbs')

  for key in db_keys:
    if key not in _DB_NAMES:
      lg.error('Unknown database table ' + key)
      raise EnvironmentError

  for key in db_keys:
    try:
      db = urllib2.urlopen(os.path.join(base_url, _DB_NAMES[key]))
    except urllib2.URLError, mesg:
      lg.error('Cannot fetch releases.db due to ' + str(mesg))
      raise EnvironmentError
    output = file(_DB_NAMES[key], 'wb')
    output.write(db.read())
    output.close()
    db.close()


def FetchUnderlyingRelease(base_url, release):
  """Obtain the list of packages in an underlying release

  This function fetches the releases Berkeley DB table of the
  underlying repository and extracts the list of packages in the
  specified release.  It also supports alias expansion in the
  underlying repository.
  """

  def DoFetch():
    db_keys = ['releases', 'aliases']
    _FetchRemoteTable(base_url, db_keys)
    return RunWithDB(db_keys, DoExtract)

  def DoExtract(_arg, dbs):
    release_db = dbs['releases']
    alias_db = dbs['aliases']
    track = release.split('/')[0]
    release_key = au.LookupAlias(alias_db, release_db, release)
    return release_db[track + '/' + release_key].split(', ')

  return ou.RunInTempDir(DoFetch)


def ImportUnderlyingTables(base_url, underlying):
  """Import the invariant underlying repository tables

  This function fetches the pkg_deps and the file_pkg Berkeley DB
  tables of the underlying repository and incorporates it into the
  corresponding table in this repository.  This data import allows us
  to perform cross-repository dependency checking.
  """

  def DoTestMissing(_arg, dbs):
    pkg_deps = dbs['pkg_deps']
    for package in underlying:
      if package not in pkg_deps:
        return True
    return False

  def DoImportWithDB(_arg, dbs):
    def DoImport():
      _FetchRemoteTable(base_url, dbs_to_import)
      return RunWithDB(dbs_to_import, DoExtract, dbs)
    ou.RunInTempDir(DoImport)

  def DoExtract(dbs, remote_dbs):
    deps = dbs['pkg_deps']
    files = dbs['file_pkg']
    remote_deps = remote_dbs['pkg_deps']
    remote_files = remote_dbs['file_pkg']
    for nva in remote_deps:
      if nva in deps:  continue
      deps[nva] = remote_deps[nva]
    for nva in remote_files:
      AppendEntry(files, nva, remote_files[nva])

  dbs_to_import = ['pkg_deps', 'file_pkg']
  if RunWithDB(['pkg_deps'], DoTestMissing):
    lg.info('Importing dependency data from ' + base_url)
    RunWithDB(dbs_to_import, DoImportWithDB)


def main(name):
  """Dump the contents of a Berkeley DB table

  The main function of the bsddb_utils module does not perform any
  debmarshal operations; it only dumps the contents of the Berkeley DB
  table given as command line argument.
  """

  lu.SetLogConsole()
  try:
    db = bsddb.btopen(name, 'r', cachesize=_CACHE_SIZE)
    for key in db:  print key + ':\n' + db[key] + '\n'
    db.close()
  except bsddb.db.DBNoSuchFileError:
    lg.error('Berkeley DB file ' + name + ' does not exist')
  except bsddb.db.DBInvalidArgError:
    lg.error('File ' + name + ' is not a valid Berkeley DB table')
  except bsddb.db.DBAccessError:
    lg.error('Cannot access file ' + name)


if __name__ == '__main__':
  if len(sys.argv) == 2:
    main(sys.argv[1])
  else:
    lg.info('Usage: ' + sys.argv[0] + ' berkeley_db_file')
