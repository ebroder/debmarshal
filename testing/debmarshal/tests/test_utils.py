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
"""tests for debmarshal.utils."""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import fcntl
import os
import posix
import unittest

import mox

from debmarshal import utils


class TestDiskIsBlockDevice(mox.MoxTestBase):
  """Test base._diskIsBlockDevice."""
  def testBlockDevice(self):
    self.mox.StubOutWithMock(os, 'stat')
    os.stat('/home/ebroder/root.img').AndReturn(posix.stat_result([
      # st_mode is the first argument
      060644, 0, 0, 0, 0, 0, 0, 0, 0, 0]))

    self.mox.ReplayAll()

    self.assertEqual(utils.diskIsBlockDevice('/home/ebroder/root.img'),
                     True)

  def testFile(self):
    self.mox.StubOutWithMock(os, 'stat')
    os.stat('/home/ebroder/root.img').AndReturn(posix.stat_result([
      0100644, 0, 0, 0, 0, 0, 0, 0, 0, 0]))

    self.mox.ReplayAll()

    self.assertEqual(utils.diskIsBlockDevice('/home/ebroder/root.img'),
                     False)


class TestAcquireLock(mox.MoxTestBase):
  """Test privops.utils.acquireLock."""
  def test(self):
    """Test acquiring a lockfile.

    Since acquiring a lock is purely procedural with no branching,
    this is a bit of a dumb test.
    """
    # When run from within a test setUp method, mox.StubOutWithMock
    # doesn't seem to be able to stub out __builtins__, so we'll hack
    # around it ourselves
    self.open = self.mox.CreateMockAnything()
    utils.open = self.open
    self.mox.StubOutWithMock(fcntl, 'lockf')

    lock_file = self.mox.CreateMock(file)
    self.open('/var/lock/debmarshal-networks', 'w+').AndReturn(lock_file)
    fcntl.lockf(lock_file, fcntl.LOCK_SH)

    self.mox.ReplayAll()

    self.assertEqual(utils.acquireLock('debmarshal-networks', fcntl.LOCK_SH),
                     lock_file)

    self.mox.VerifyAll()

    del utils.open


class TestWithLockfile(mox.MoxTestBase):
  """Test the privops.utils.withLockfile decorator."""
  def test(self):
    """Test wrapping a function in a file-based lock."""
    lock_file = self.mox.CreateMock(file)
    self.mox.StubOutWithMock(utils, 'acquireLock')
    utils.acquireLock('debmarshal', fcntl.LOCK_EX).AndReturn(lock_file)

    self.mox.ReplayAll()

    @utils.withLockfile('debmarshal', fcntl.LOCK_EX)
    def hasALock():
      return True

    self.assertEqual(hasALock(), True)


class TestParseKBytes(unittest.TestCase):
  """Test utils.parseKBytes."""
  def testGB(self):
    """Test amount with GB suffix."""
    self.assertEqual(utils.parseKBytes("15G"), 15728640)

  def testP(self):
    """Test amount with just 'P' for suffix."""
    self.assertEqual(utils.parseKBytes("2P"), 2199023255552)

  def testMiB(self):
    """Test amount with MiB suffix."""
    self.assertEqual(utils.parseKBytes("8MiB"), 8192)

  def testK(self):
    """Make sure that parseKBytes does the right thing with kilobytes."""
    self.assertEqual(utils.parseKBytes("12K"), 12)
