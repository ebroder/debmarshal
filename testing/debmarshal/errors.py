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
"""debmarshal exception classes."""

__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


class Error(Exception):
  """Base exception for debmarshal."""


class InvalidInput(Error):
  """Input didn't pass validation."""


class AccessDenied(Error):
  """User does not have permission to perform the requested action."""


class NotFound(Error):
  """Some object could not be found."""


class DomainNotFound(NotFound):
  """The referenced domain couldn't be found."""


class NetworkNotFound(NotFound):
  """The referenced network couldn't be found."""


class NotImplementedError(Error):
  """This method should have been overridden in a subclass."""


class NoAvailableIPs(Error):
  """No available subnet could be found."""
