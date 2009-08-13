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
from debmarshal import utils


caller = None


def coerceDbusType(arg):
  """Coerce a dbus type into the normal Python types.

  Because types like the integers don't have useful superclasses, we
  have to more or less exhaustively loop through the types that we
  know about.

  This will recursively coerce members of structs, arrays, and dicts as
  well.

  Args:
    arg: An object with one of the DBus types, to be converted.

  Returns:
    The argument, coerced into the standard set of Python types.
  """
  # First the collection types
  if isinstance(arg, dbus.Struct):
    return tuple(coerceDbusType(i) for i in arg)
  elif isinstance(arg, dbus.Array):
    return list(coerceDbusType(i) for i in arg)
  elif isinstance(arg, dbus.Dictionary):
    return dict((coerceDbusType(k), coerceDbusType(v))
                for k, v in arg.iteritems())
  # Then the scalars
  elif isinstance(arg, (dbus.ByteArray, dbus.UTF8String,
                        dbus.ObjectPath, dbus.Signature)):
    return str(arg)
  elif isinstance(arg, dbus.String):
    return unicode(arg)
  elif isinstance(arg, dbus.Boolean):
    return bool(arg)
  elif isinstance(arg, dbus.Double):
    return float(arg)
  # And everything else looks like an int
  elif isinstance(arg, (dbus.Byte, dbus.Int16, dbus.Int32, dbus.Int64,
                        dbus.UInt16, dbus.UInt32, dbus.UInt64)):
    return int(arg)
  # And that's everything - anything else must have started life as a
  # Python type.
  else:
    return arg


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

  dbus_obj = dbus.SystemBus().get_object('org.freedesktop.DBus',
                                          '/org/freedesktop/DBus')
  return int(dbus_obj.GetConnectionUnixUser(
      caller, dbus_interface='org.freedesktop.DBus'))


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
  lock = utils.acquireLock(filename, fcntl.LOCK_SH)
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
  lock = utils.acquireLock(filename, fcntl.LOCK_EX)
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
