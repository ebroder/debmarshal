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


"""Release alias handling utility functions

The alias_utils module contains utility functions for dealing with
the release aliases in a maintenance track.
"""

__author__ = 'cklin@google.com (Chuan-Kai Lin)'

import logging as lg
import os
import sys
import time
import bsddb_utils as bu
import os_utils as ou
import setting_utils as su


def _ValidateAlias(alias):
  """Check that an alias is syntactically well-formed

  This function accepts a 'track/alias' string and check that it
  contains a / character somewhere in the middle of the string.
  """

  if alias.find('/') < 1:
    lg.error('Alias should contain the track name before /')
  elif alias.endswith('/'):
    lg.error('Alias should contain the alias name after /')
  elif alias.split('/', 1)[1].find('/') >= 0:
    lg.error('Alias name should not contain a / character')
  elif alias.split('/', 1)[1].isdigit():
    lg.error('Alias name must contain a non-digit character')
  else:
    return
  sys.exit()


def UpdateAlias(alias_db, release_db, alias, release):
  """Update an alias to point to the given release

  This function appends an entry in the aliases Berkeley DB table to
  record that the specified alias is changed to point to the given
  release at this time.  The release can be specified as an alias.  It
  does not actually change the symlinks -- for that you need to use
  the RefreshAlias() function.
  """

  _ValidateAlias(alias)
  track = alias.split('/')[0]
  release = LookupAlias(alias_db, release_db, track + '/' + release)
  ts = str(time.time())
  bu.AppendEntry(alias_db, alias, ts+'_'+release)


def RefreshAlias(alias_db):
  """Refresh all the release alias symlinks in dists/

  This function removes all symlinks at the top-level directory of
  each maintenance track and re-create the alias symlinks from the
  records in the aliases Berkeley DB table.
  """

  for track in su.ListTracks():
    track_dir = os.path.join('dists', track)
    if not os.path.isdir(track_dir):  continue
    files = os.listdir(track_dir)
    for name in files:
      name = os.path.join(track_dir, name)
      if os.path.islink(name):
        ou.IgnoreOSError(os.remove, name)

  for alias in alias_db:
    name = os.path.join('dists', alias)
    release = alias_db[alias].split('_')[-1]
    os.symlink(release, name)


def LookupAlias(alias_db, release_db, alias):
  """Convert an 'track/alias' string to a release number
  """

  [track, release] = alias.split('/')
  if alias in alias_db:
    release = alias_db[alias].split(', ')[-1].split('_')[-1]
  if (track + '/' + release) not in release_db:
    lg.error(alias + ' does not refer to a release')
    sys.exit()
  return release


def ShowAliasHistory(alias_db, alias):
  """Display the change history of the given alias
  """

  _ValidateAlias(alias)
  if alias not in alias_db:
    lg.error('There is no such an alias called ' + alias)
    sys.exit()
  print 'History for alias', alias
  for line in alias_db[alias].split(', '):
    [ts, release] = line.split('_', 1)
    print release + '\t' + time.asctime(time.localtime(float(ts)))
