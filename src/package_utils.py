#!/usr/bin/python2.4
#
# Copyright 2006 Google Inc. All Rights Reserved.

"""Deb control file parsing utility functions

The package_utils module contains utility functions for dealing with
control files (binary package control file, .dsc file, .changes file,
Packages file, etc.) which also may possibly be signed.
"""

__author__ = 'cklin@google.com (Chuan-Kai Lin)'

import logging as lg
import os
import re
import setting_utils as su


def StripSignature(lines):
  """Extract clear-signed message in RFC2440 OpenPGP format

  This function accepts a cleartext signature format file and extracts
  the signed message without verifying the signature.  If the input
  text does not contain a signature, the function returns the original
  input unchanged.  If the input text contains malformed signature,
  the function returns None.
  """

  header = '-----BEGIN PGP SIGNED MESSAGE-----'
  hash_header = 'Hash: '
  dash_escape = '- -'
  begin_armor = '-----BEGIN PGP SIGNATURE-----'
  end_armor = '-----END PGP SIGNATURE-----'

  stage = 1
  result = []
  original = []

  # The function is organized as a state machine.  The conditionals in
  # the loop check for expected headers and advance the state.

  for line in lines:
    line = line.rstrip('\n')
    original.append(line)

    # -----BEGIN PGP SIGNED MESSAGE-----

    if stage == 1:
      if line == header:
        stage = 2
      continue

    # Hash: SHA1 (or MD5 or whatsoever), followed by empty line.

    elif stage == 2:
      if line.startswith(hash_header):
        continue
      if not line:
        stage = 3
        continue

    # -----BEGIN PGP SIGNATURE----- (ends signed text)

    elif stage == 3:
      if line == begin_armor:
        stage = 4
        continue
      elif line.startswith(dash_escape):
        result.append(line[2:])
        continue
      elif not line or line[0] != '-':
        result.append(line)
        continue

    # -----END PGP SIGNATURE----- (ends signature)

    elif stage == 4:
      if line == end_armor:
        stage = 5
        break
      continue
    break

  if stage == 5:
    return result
  if stage == 1:
    lg.warning('Input text does not contain OpenPGP signature')
    return original
  else:
    lg.warning('Text contains malformed OpenPGP signature')
    return None


def ParseAttributes(lines):
  """Parse control file and extract attributes

  The deb package format and release workflow relies heavily on text
  files that define attributes in colon-separated lines (Policy 5.1).
  This function parses the contents of these files and stores the
  results in a dictionary.
  """

  attr_re = re.compile(r'(\w|-)+: \S+')
  key_re = re.compile(r'(\w|-)+:\s*\Z')
  attr_dict = {}
  key = None
  single = False

  for line in lines:
    line = line.rstrip('\n')

    # An attribute with value after colon.  This line may be an
    # attribute in itself or the first line of a multi-line attribute.

    if attr_re.match(line):
      [key, value_str] = line.split(': ', 1)
      values = value_str.split(', ');
      attr_dict[key] = values
      single = True

    # An attribute with no values after colon.  This line must be the
    # first of a multi-line attribute.

    elif key_re.match(line):
      key = line.split(':', 1)[0]
      attr_dict[key] = []
      single = False

    # A line that starts with space must be a continuation of a
    # multi-line attribute (if it comes after an attribute line) or
    # junk (if it comes after a malformed line).

    elif line and line[0].isspace():
      if key is not None:
        if single:
          attr_dict[key] = [', '.join(attr_dict[key])]
        attr_dict[key].append(line[1:])
        single = False

    # Everything else is malformed garbage.

    else:
      key = None
  return attr_dict


def GetPathInPool(source_pkg):
  """Determine where in the pool hierarchy to put a source package
  """

  if not source_pkg:
    lg.error('Source package name is an empty string')
    raise ValueError
  if source_pkg.find('/') >= 0:
    lg.error('Source package name ' + source_pkg +
             ' contains the / character')
    raise ValueError

  initial = ''
  component = su.GetSetting(None, 'Component')
  if source_pkg.startswith('lib') and len(source_pkg) > 3:
    initial = source_pkg[:4]
  else:
    initial = source_pkg[0]
  return os.path.join('pool', component, initial, source_pkg)


def GetPackageID(attr_dict):
  """Return the name_version_arch string from binary package metadata
  """

  name = attr_dict['Package'][0]
  ver = attr_dict['Version'][0]
  arch = attr_dict['Architecture'][0]
  return '_'.join([name, ver, arch])


def GetSourceID(attr_dict):
  """Return the name_version string from source package metadata
  """

  name = attr_dict['Source'][0]
  ver = attr_dict['Version'][0]
  return '_'.join([name, ver])
