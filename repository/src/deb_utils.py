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


"""Deb package parsing and analysis functions

The deb_utils module contains utility functions for extracting the
metadata in source and binary package files, collecting relevant data
on the files themselves, and storing the results to Berkeley DB tables
for later use.
"""

__author__ = 'cklin@google.com (Chuan-Kai Lin)'

import logging as lg
import os
import sys
import tarfile
import bsddb_utils as bu
import crypto_utils as cu
import os_utils as ou
import package_utils as pu


def ParseDebInfo(name):
  """Extract package metadata from a binary package file

  This function unpacks the specified binary package file and returns
  two items: a dictionary representing the package control file, and a
  list of files provided by the package.
  """

  def DoListContents(data):
    return [os.path.normpath(s) for s in data.getnames()
            if not s.endswith('/')]

  def DoParseControl(control):
    mf = control.extractfile('control')
    attr_dict = pu.ParseAttributes(mf.readlines())
    mf.close()
    return attr_dict

  def DoExtract():
    ou.SpawnProgram(['/usr/bin/ar', 'x', name])
    contents = ou.RunWithTarInput(DoListContents, 'data')
    attr_dict = ou.RunWithTarInput(DoParseControl, 'control')
    return (contents, attr_dict)

  if not os.path.exists(name):
    lg.error('Package file ' + name + ' does not exist')
    raise EnvironmentError
  return ou.RunInTempDir(DoExtract)


# These are the attributes in the pkg_deps Berkeley DB table.

_DEP_KEYS = ['Component', 'Essential', 'Source', 'Depends',
             'Pre-Depends', 'Conflicts', 'Provides', 'Replaces']


def BuildDependencyString(name, attr_dict):
  """Construct the pkg_deps entry of a binary package

  This function takes the name and control-file attribute dictionary
  of a binary package and constructs the pkg_deps table string for the
  package.  The first three attributes require special treatment, and
  the remaining ones are copied verbatim from the dictionary.
  """

  # Component: all udeb packages go into the debian-installer
  # subcomponent of whatever component given in the control file.

  string = name.split('/')[1]
  if name.endswith('.udeb'):
    string = string + '/debian-installer'
  string = string + '\n'

  # Essential: set default value to 'no'.

  string = string + attr_dict.get('Essential', ['no'])[0] + '\n'

  # Source: interpret in accordance with Policy 5.6.1; this is the
  # authority on how source and binary packages relate.  Information
  # in .dsc files are incomplete because there is no way to determine
  # the version number of binary packages (which may differ from that
  # of source packages).

  pkg = attr_dict['Package'][0]
  ver = attr_dict['Version'][0]
  if 'Source' in attr_dict:
    parts = attr_dict['Source'][0].split('(')
    pkg = parts[0].strip()
    if len(parts) == 2:
      ver = parts[1][:-1]
  string = string + pkg + '_' + ver + '\n'

  # Everything else we copy verbatim.

  for key in _DEP_KEYS[3:]:
    string = string + ', '.join(attr_dict.get(key, [])) + '\n'
  return string


def _ParseDependencyString(string):
  """Parse a pkg_deps and return an attribute dictionary

  This function is the inverse of BuildDependencyString(): it takes an
  entry from the pkg_deps table and returns an attribute dictionary.
  """

  values = string.splitlines()
  if len(values) != len(_DEP_KEYS):
    lg.error('Malformed dependency string ' + string)
    raise ValueError

  attr_dict = {}
  index = 0;
  for key in _DEP_KEYS:

    # We need special treatment here because ''.split() returns ['']
    # instead of the empty list [].

    if values[index] == '':
      attr_dict[key] = []
    else:
      attr_dict[key] = values[index].split(', ')
    index = index+1
  return attr_dict


def ParseDependencyTable(dep_table):
  """Parse the pkg_deps Berkeley DB table to a dictionary
  """

  dep_dict = {}
  for nva in dep_table:
    dep_dict[nva] = _ParseDependencyString(dep_table[nva])
  return dep_dict


def BuildDebInfoText(name, attr_dict):
  """Build binary package information text for Packages

  This function builds the information text for a binary package in
  the form that is ready for verbatim inclusion into the Packages
  file.  Typically the return value of this function goes into the
  pkg_info Berkeley DB table.
  """

  keys = ['Package', 'Essential',
          'Priority', 'Section', 'Installed-Size',
          'Maintainer', 'Architecture', 'Source', 'Version',
          'Replaces', 'Provides', 'Depends', 'Pre-Depends',
          'Recommends', 'Suggests', 'Conflicts']

  string = ''
  for key in keys:
    value = attr_dict.get(key, [])
    if not value:  continue
    string = string + key + ': ' + ', '.join(value) + '\n'

  return (string + 'Filename: ' + name + '\n' +
          'Size: ' + str(os.path.getsize(name)) + '\n' +
          'MD5sum: ' + cu.GetMD5Hash(name) + '\n' +
          'Description: ' + '\n '.join(attr_dict['Description']))


def BuildSrcInfoText(name, attr_dict):
  """Build source package information text for Sources

  This function builds the information text for a source package in
  the form that is ready for verbatim inclusion into the Sources file.
  Typically the return value of this function goes into the src_info
  Berkeley DB table.
  """

  keys = ['Binary', 'Version', 'Priority', 'Section',
          'Maintainer', 'Build-Depends', 'Architecture',
          'Standards-Version', 'Format']

  string = 'Package: ' + attr_dict['Source'][0] + '\n'
  for key in keys:
    value = attr_dict.get(key, [])
    if not value:  continue
    string = string + key + ': ' + ', '.join(value) + '\n'

  path, dsc = os.path.split(name)
  return (string + 'Directory: ' + path + '\n' +
          'Files:\n ' + cu.GetMD5Hash(name) +
          ' ' + str(os.path.getsize(name)) + ' ' + dsc + '\n ' +
          '\n '.join(attr_dict['Files']))
