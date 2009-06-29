# -*- python-indent: 2; py-indent-offset: 2 -*-
"""debmarshal exception classes"""

__authors__ = [
  'Evan Broder <ebroder@google.com>',
]


class Error(Exception):
  """Base exception for debmarshal"""
  pass

class InvalidInput(Error):
  """Input didn't pass validation"""
  pass

class AccessDenied(Error):
  pass

class NotFound(Error):
  """Some object could not be found"""
  pass

class NetworkNotFound(NotFound):
  """The referenced network couldn't be found"""
  pass
