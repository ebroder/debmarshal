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
"""General use utility functions for debmarshal."""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import fcntl
import os
import stat

import decorator


def diskIsBlockDevice(disk):
  """Identify whether a particular disk is an image file or block
  device

  Args:
    disk: Path to the disk image being tested

  Returns:
    True if the disk is a block device; False if it's a file
  """
  return stat.S_ISBLK(os.stat(disk).st_mode)


def acquireLock(filename, mode):
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
    lock = acquireLock(filename, mode)
    return f(*args, **kwargs)

  return _withLockfile
