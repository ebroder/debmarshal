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

import dbus
import decorator
import libvirt
import yaml

from debmarshal import errors


caller = None


def getCaller():
  """Find what UID called into a privileged function.

  This function exists to allow privileged functions to find out what
  user called them without needing to be aware of the means by which
  debmarshal escalated privilege.

  Returns:
    The UID of the user that called a privileged function.
  """
  if caller is None:
    # If the call didn't come in through dbus, someone must have had
    # privilege to begin with.
    return 0

  dbus_obj = dbus.StarterBus().get_object('org.freedesktop.DBus',
                                          '/org/freedesktop/DBus')
  return int(dbus_obj.GetConnectionUnixUser(
      caller, dbus_interface='org.freedesktop.DBus'))


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
