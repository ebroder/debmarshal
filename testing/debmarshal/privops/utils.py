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
"""
debmarshal utilities for privileged operations

This module contains the functions needed to support privileged
operations, by separating the act of gaining privilege from actually
using that privilege.
"""


__authors__ = [
  'Evan Broder <ebroder@google.com>',
]


import os
import subprocess
import sys

import decorator
import yaml

from debmarshal import config
from debmarshal import errors


_SETUID_BINARY = os.path.join(config.libexecdir, 'debmarshpriv')


_subcommands = {}


def runWithPrivilege(subcommand):
  """Decorator for wrapping a function to ensure that it gets run with
  privileges by using a small setuid wrapper binary.

  If a function wrapped with runWithPrivilege is called by a non-root
  user, execute the setuid wrapper with the arguments passed in.

  If a function is re-executed through the setuid wrapper, the
  function arguments and keyword arguments are passed in through the
  command line in YAML.

  For security reasons, all YAML dumps and loads occur using the
  "safe" parser, which will only (de-)serialize built-in types. This
  means that arguments to and return values from functions wrapped in
  runWithPrivilege must be limited to built-ins.

  The return value or raised exceptions of the function are also
  passed from the setuid subprocess back to the caller via standard
  out, so functions wrapped in runWithPrivilege shouldn't print
  anything.

  Args:
    subcommand: This is used as the first argument to the setuid
      binary. Since the setuid binary simply executes this module, the
      subcommand is also tracked internally for dispatching
  """
  @decorator.decorator
  def _runWithPrivilege(f, *args, **kwargs):

    # If we already have our privileges
    if os.geteuid() == 0:
      return f(*args, **kwargs)
    else:

      # Make sure that the setuid binary is actually setuid root so
      # we don't get stuck in a loop
      stats = os.stat(_SETUID_BINARY)
      if not (stats.st_mode & 04000 and stats.st_uid == 0):
        raise errors.Error('%s is not setuid root' % _SETUID_BINARY)

      p = subprocess.Popen([_SETUID_BINARY,
                            subcommand,
                            yaml.safe_dump(args),
                            yaml.safe_dump(kwargs)],
                           stdin=None,
                           stdout=subprocess.PIPE,
                           close_fds=True)
      rc = p.wait()

      # This is the only place we don't use yaml.safe_load. That's
      # intentional, because the source of this string is trusted, and
      # may be an object like an exception.
      ret = yaml.load(p.stdout)
      if rc:
        raise ret
      else:
        return ret

  # The extra layer of redirection is needed if we want to both (a)
  # use the decorator module (we do, because it gives us nice
  # function-signature-preserving properties) and (b) associate a
  # subcommand with the function it's wrapping at parse time.
  def _makeRunWithPriv(f):
    _subcommands[subcommand] = f
    return _runWithPrivilege(f)

  return _makeRunWithPriv


def getCaller():
  """Find what UID called into a privileged function.

  This function exists to allow other functions wrapped in
  runWithPrivilege to find out what user called them without needing
  to be aware of the means by which runWithPrivileges escalates
  itself.

  Returns:
    The UID of the user that called a privileged function.
  """
  return os.getuid()


def usage():
  """Command-line usage information for debmarshal.privops.

  Normal users are never expected to trigger this, because normal
  users are never supposed to run debmarshal.privops directly; instead
  other debmarshal scripts should use functions in this module, which
  results in the setuid re-execution.

  But just in case someone runs it directly, we'll tell them what it
  does.
  """
  print >>sys.stderr, ("Usage: %s subcommand args kwargs" %
                       os.path.basename(sys.argv[0]))
  print >>sys.stderr
  print >>sys.stderr, "  args is a YAML-encoded list"
  print >>sys.stderr, "  kwargs is a YAML-encoded dict"


def main(args):
  """Dispatch module invocations.

  A sort of other half of the runWithPrivilege decorator, main parses
  the arguments and kwargs passed in on the command line and calls the
  appropriate function. It also intercepts any raised exceptions or
  return values, serializes them, and passes them over standard out to
  whatever invoked the module.

  Note: this doesn't intercept exceptions raised as part of the
  initial argument parsing, because we're optimistically assuming that
  arguments that come in from runWithPrivilege are flawless
  (heh...). Those exceptions will get rendered by the Python
  interpreter to standard error, as will any errors that we generate.

  Args:
    args, a list of arguments passed in to the module, not including
      argv[0]

  Returns:
    Return an integer, which becomes the exit code for when the module
      is run as a script.
  """
  if len(args) != 3:
    usage()
    return 1

  subcommand, posargs, kwargs = args
  posargs = yaml.safe_load(posargs)
  kwargs = yaml.safe_load(kwargs)

  priv_func = _subcommands[subcommand]

  try:
    ret = priv_func(*posargs, **kwargs)
    rc = 0
  except Exception, e:
    ret = e
    rc = 1

  # This is the only place we don't use yaml.safe_dump, because this
  # output is trusted when it gets parsed, and we want to be able to
  # pass around arbitrary objects
  print yaml.dump(ret)
  return rc
