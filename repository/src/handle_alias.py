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

"""Script to manipulate release aliases

The handle_alias.py script is a repository-administrator command used
for inspecting and manipulating release aliases.  Release aliases are
effectively managed symlinks with a fully-logged history.
"""

__author__ = 'cklin@google.com (Chuan-Kai Lin)'

import logging as lg
import sys
import alias_utils as au
import bsddb_utils as bu
import logging_utils as lu


def _DoRefresh(_arg, dbs):
  alias_db = dbs['aliases']
  au.RefreshAlias(alias_db)


def _DoUpdate((alias, release), dbs):
  alias_db = dbs['aliases']
  release_db = dbs['releases']
  au.UpdateAlias(alias_db, release_db, alias, release)
  au.RefreshAlias(alias_db)


def _DoShowLog(alias, dbs):
  alias_db = dbs['aliases']
  au.ShowAliasHistory(alias_db, alias)


def main():
  lu.SetLogConsole()

  if len(sys.argv) < 2:
    lg.error('You need to provide a command: refresh, log, or update')
    sys.exit(0)

  if (sys.argv[1]) == 'refresh':
    bu.RunWithDB(['aliases'], _DoRefresh)
  elif (sys.argv[1]) == 'update':
    if len(sys.argv) != 4:
      lg.error('update needs two arguments: alias and release')
      sys.exit()
    alias = sys.argv[2]
    release = sys.argv[3]
    bu.RunWithDB(['aliases', 'releases'], _DoUpdate, (alias, release))
  elif (sys.argv[1]) == 'log':
    if len(sys.argv) != 3:
      lg.error('update needs an argument: alias')
      sys.exit()
    alias = sys.argv[2]
    bu.RunWithDB(['aliases'], _DoShowLog, alias)
  else:
    lg.error(sys.argv[1] + ' is not a valid command')


if __name__ == '__main__':
  main()
