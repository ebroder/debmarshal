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
"""debmarshal utilities for privileged operations.

This module contains the functions needed to support privileged
operations, by separating the act of gaining privilege from actually
using that privilege.
"""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import errno
import fcntl
import os
try:
  import cPickle as pickle
except ImportError:  # pragma: no cover
  import pickle
import subprocess
import sys

import decorator
import libvirt
import yaml

from debmarshal import config
from debmarshal import errors


_SETUID_BINARY = os.path.join(config.libexecdir, 'debmarshpriv')


_subcommands = {}


def runWithPrivilege(subcommand):
  """Decorator for running a function with privileges.

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


def _acquireLock(filename, mode):
  """Acquire a lock at a given path.

  Return a file descriptor to filename with the requested lock. It is
  the caller's responsibility to keep that fd in scope until the lock
  should be released.

  This function was extracted from withLockfile, loadState, etc. to
  simplify test mocks.

  It should be noted that this is one of those great power-great
  responsibility functions. Callers must be careful to never call
  another function that acquires a lock on the same filename, as that
  will cause the outer function to lose the lock.

  Args:
    filename: The basename of the lockfile to use; filename is
      appended to /var/lock/ to find the full path to lock
    mode: Either fcntl.LOCK_SH or fcntl.LOCK_EX

  Returns:
    A python file descriptor (i.e. instance of class file) for the
      file requested with an active advisory lock.
  """
  lock = open('/var/lock/%s' % filename, 'w+')
  fcntl.lockf(lock, mode)
  return lock


def withLockfile(filename, mode):
  """Decorator for executing function with a lock held.

  A function that is wrapped with withLockfile will acquire the lock
  filename in /var/lock before execution and release it afterwards.

  Args:
    filename: The basename of the lockfile to use; filename is
      appended to /var/lock/ to find the full path to lock
    mode: Either fcntl.LOCK_SH or fcntl.LOCK_EX
  """
  @decorator.decorator
  def _withLockfile(f, *args, **kwargs):
    lock = _acquireLock(filename, mode)
    return f(*args, **kwargs)

  return _withLockfile


def loadState(filename):
  """Load state from a file in /var/run.

  debmarshal stores state as pickles in /var/run, using files with
  corresponding names in /var/lock for locking.

  Args:
    filename: The basename of the state file to load.

  Returns:
    The depickled contents of the state file, or None if the state
      file does not yet exist.
  """
  lock = _acquireLock(filename, fcntl.LOCK_SH)
  try:
    state_file = open('/var/run/%s' % filename)
    return pickle.load(state_file)
  except EnvironmentError, e:
    if e.errno == errno.ENOENT:
      return
    else:
      raise


def storeState(state, filename):
  """Store state to a file in /var/run.

  This stores state to a pickle in /var/run, including locking in
  /var/lock that should be compatible with loadState.

  Args:
    state: The state to pickle and store.
    filename: The basename of the state file to save to.
  """
  lock = _acquireLock(filename, fcntl.LOCK_EX)
  state_file = open('/var/run/%s' % filename, 'w')
  pickle.dump(state, state_file)


@decorator.decorator
def withoutLibvirtError(f, *args, **kwargs):
  """Decorator to unset the default libvirt error handler.

  The default libvirt error handler prints any errors that occur to
  stderr. Since the Python bindings simultaneously throw an exception,
  this behavior is redundant, not to mention potentially confusing to
  users, who might be seeing error messages that were otherwise
  handled.

  withoutLibvirtError will set a new error handler that ignores
  errors, allowing them to bubble up as exceptions instead. So that
  withoutLibvirtError can be used on functions that might call each
  other, and because it is never desirable for the default error
  handler to be used in debmarshal, withoutLibvirtError does not reset
  the error handler to its default.

  Any function that is expected to generate libvirt errors in the
  course of regular operation should be wrapped in
  withoutLibvirtError.
  """
  _clearLibvirtError()
  return f(*args, **kwargs)


def _clearLibvirtError():
  """Disable libvirt error messages.

  _clearLibvirtError is a helper function to withoutLibvirtError,
  designed to make mocks and testing easy. It simply registers NOOP
  error handler for libvirt.
  """
  libvirt.registerErrorHandler((lambda ctx, err: 1), None)


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
