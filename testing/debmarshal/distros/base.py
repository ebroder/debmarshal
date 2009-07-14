#!/usr/bin/python
# -*- python-indent: 2; py-indent-offset: 2 -*-
# Copyright 2009 Google Inc.
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
"""Base for debmarshal's distribution representation classes."""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


from debmarshal import errors


class Distribution(object):
  """Superclass representation of an abstract Linux distribution.

  Classes derived from Distribution represent Linux distributions and
  the mechanism by which one can be installed/imaged.

  The code and comments refer a lot to Linux distributions.  This
  class could potentially be used for any operating system for which
  an unattended install is possible, although whether it can be booted
  depends a lot on the specific virtualization technology being used.

  For a distribution install, there are two stages. The first stage
  installs a completely uncustomized base OS; the second customizes
  the base image for use with a particular test case.

  Both stages can have a set of configuration options, some of which
  can be set by users of the distribution class, some which can't be,
  and some which must be. Together, these options can be used to
  uniquely identify a given snapshot.

  Attributes:
    base_defaults: A dict with the default configuration options for
      the base image.
    base_required: A set of option names that must be set by users of
      the distribution class
    base_configurable: A set of option names that can be set by users
      of the distribution. This should not include the elements of
      base_required.
    custom_defaults: The default configuration options for the stage
      2 image.
    custom_required: The set of option names that must be set for
      stage 2.
    custom_configurable: The set of option names that can be set by
      users for stage 2. This should not include custom_required.
  """
  base_defaults = {}

  base_required = set()

  base_configurable = set()

  custom_defaults = {}

  custom_required = set()

  custom_configurable = set()
