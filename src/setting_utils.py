#!/usr/bin/python2.4
#
# Copyright 2006 Google Inc. All Rights Reserved.

"""Repository configuration utility functions

The setting_utils module contains utility functions for accessing the
repository and maintenance-track configurable settings.  This module
does not deal with the release specification file; see
ru.FilterVersionWithFile() for that functionality.
"""

__author__ = 'cklin@google.com (Chuan-Kai Lin)'

import logging as lg
import sys
import package_utils as pu
import os_utils as ou


_settings = None


def _LoadSettings():
  """Load the configuration file into the _settings dictionary
  """

  global _settings

  if _settings is None:
    _settings = ou.RunWithFileInput(_ParseConfig, 'config/repository')
    if _settings is None:
      lg.error('Cannot load repository settings')
      sys.exit()


def _ParseConfig(lines):
  """Parse the contents of a configuration file

  This function parses a configuration file and returns a dictionary
  containing the results.  It splits the input into sections by
  bracket-quoted headings, and store the attributes in each section in
  a separate dictionary indexed by the section name.  The top-level
  section is indexed by the key None.
  """

  repo_dict = {}
  track_id = None
  track_lines = []

  for line in lines:
    line = line.split('#')[0]
    if line == '' or line.isspace():  continue
    if line.startswith('[') and line.endswith(']\n'):
      repo_dict[track_id] = pu.ParseAttributes(track_lines)
      track_id = line[1:-2]
      track_lines = []
    else:
      track_lines.append(line.rstrip())

  repo_dict[track_id] = pu.ParseAttributes(track_lines)
  repo_dict[None].setdefault('Component', ['local'])
  repo_dict[None].setdefault('Architectures', ['i386'])
  return repo_dict


def GetSetting(track, key):
  """Get a setting attribute in a maintenance track
  """

  _LoadSettings()
  if track in _settings:
    if key in _settings[track]:
      return ', '.join(_settings[track][key])
  if key in _settings[None]:
    return ', '.join(_settings[None][key])
  return None


def ListTracks():
  """List all tracks mentioned in the configuration file
  """

  _LoadSettings()
  tracks = ['snapshot']
  for track in _settings:
    if track is None:  continue
    tracks.append(track)
  return tracks


def ConfirmTrack(track):
  """Check that the given track is valid (exit on error)
  """

  _LoadSettings()
  if track == 'snapshot':  return
  if track not in _settings:
    lg.error('There is no such a track called ' + track)
    sys.exit()
