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
"""tests for debmarshal._privops.utils"""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import errno
import fcntl
import os
try:
  import cPickle as pickle
except ImportError:
  import pickle
try:
  import cStringIO as StringIO
except ImportError:
  import StringIO
import unittest

import dbus
import libvirt
import mox

from debmarshal import errors
from debmarshal._privops import utils


class TestGetCaller(mox.MoxTestBase):
  """Test for privops.utils.getCaller"""
  def testCallerUnset(self):
    """Verify that utils.getCaller returns 0 if not run through dbus."""
    utils.caller = None

    self.assertEquals(utils.getCaller(), 0)

  def testCallerSet(self):
    """Verify that privops.utils.getCaller uses dbus correctly.

    getCaller should be connecting to the bus that spawned the
    privileged daemon.

    This is sort of a dumb test, because it's hard to test code that
    interacts with dbus in isolation, but at least it'll start failing
    if we change the mechanisms by which debmarshal escalates
    privileges.
    """
    utils.caller = ':1:13'
    uid = 500

    bus = self.mox.CreateMock(dbus.bus.BusConnection)
    dbus_obj = self.mox.CreateMockAnything()

    self.mox.StubOutWithMock(dbus, 'StarterBus', use_mock_anything=True)

    dbus.StarterBus().AndReturn(bus)
    bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus').AndReturn(
        dbus_obj)
    dbus_obj.GetConnectionUnixUser(
        utils.caller, dbus_interface='org.freedesktop.DBus').\
        AndReturn(dbus.UInt32(uid))

    self.mox.ReplayAll()

    self.assertEquals(utils.getCaller(), uid)

    utils.caller = None


class TestAcquireLock(mox.MoxTestBase):
  """Test privops.utils._acquireLock."""
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

    self.assertEqual(utils._acquireLock('debmarshal-networks', fcntl.LOCK_SH),
                     lock_file)

    self.mox.VerifyAll()

    del utils.open


class TestWithLockfile(mox.MoxTestBase):
  """Test the privops.utils.withLockfile decorator."""
  def test(self):
    """Test wrapping a function in a file-based lock."""
    lock_file = self.mox.CreateMock(file)
    self.mox.StubOutWithMock(utils, '_acquireLock')
    utils._acquireLock('debmarshal', fcntl.LOCK_EX).AndReturn(lock_file)

    self.mox.ReplayAll()

    @utils.withLockfile('debmarshal', fcntl.LOCK_EX)
    def hasALock():
      return True

    self.assertEqual(hasALock(), True)


class TestLoadState(mox.MoxTestBase):
  """Test loading state from /var/run."""
  def setUp(self):
    """Stub out acquiring the lock."""
    super(TestLoadState, self).setUp()

    lock_file = self.mox.CreateMock(file)
    self.mox.StubOutWithMock(utils, '_acquireLock')
    utils._acquireLock('debmarshal-networks', fcntl.LOCK_SH).\
        AndReturn(lock_file)

    self.open = self.mox.CreateMockAnything()
    utils.open = self.open

  def tearDown(self):
    """Undo the mock open() function."""
    del utils.open

    super(TestLoadState, self).tearDown()

  def testNoStateFile(self):
    """Make sure that loadState returns None if the file doesn't exist."""
    e = IOError(errno.ENOENT,"ENOENT")
    self.open('/var/run/debmarshal-networks').AndRaise(e)

    self.mox.ReplayAll()

    self.assertEqual(utils.loadState('debmarshal-networks'), None)

  def testExceptionOpeningStateFile(self):
    """Make sure that any exception other than ENOENT raised opening
    the state file is re-raised"""
    e = IOError(errno.EACCES, "EACCES")
    self.open('/var/run/debmarshal-networks').AndRaise(e)

    self.mox.ReplayAll()

    self.assertRaises(IOError, utils.loadState, 'debmarshal-networks')

  def testSuccess(self):
    """Test successfully loading a state file."""
    data = ['foo', 'bar']
    state = StringIO.StringIO(pickle.dumps(data))
    self.open('/var/run/debmarshal-networks').AndReturn(state)

    self.mox.ReplayAll()

    self.assertEqual(data, utils.loadState('debmarshal-networks'))


class TestStoreState(mox.MoxTestBase):
  """Test debmarshal._privops.utils.storeState."""
  def test(self):
    """Dumb test for privops.utils.storeState.

    This test is pretty dumb. There are no branches or anything in
    storeState, and if the code doesn't throw exceptions, it's roughly
    guaranteed to work."""
    self.networks = [('debmarshal-0', 500, '10.100.1.1')]

    lock_file = self.mox.CreateMock(file)
    self.mox.StubOutWithMock(utils, '_acquireLock')
    utils._acquireLock('debmarshal-networks', fcntl.LOCK_EX).\
        AndReturn(lock_file)

    self.open = self.mox.CreateMockAnything()
    utils.open = self.open

    net_file = self.mox.CreateMock(file)
    self.open('/var/run/debmarshal-networks', 'w').AndReturn(net_file)
    pickle.dump(self.networks, net_file)

    self.mox.ReplayAll()

    utils.storeState(self.networks, 'debmarshal-networks')

    self.mox.VerifyAll()

    del utils.open


class TestWithoutLibvirtError(mox.MoxTestBase):
  """Test privops.utils.withoutLibvirtError."""
  def test(self):
    self.mox.StubOutWithMock(utils, '_clearLibvirtError')
    utils._clearLibvirtError()

    self.mox.ReplayAll()

    @utils.withoutLibvirtError
    def func():
      return 1

    self.assertEqual(func(), 1)


class TestClearLibvirtError(mox.MoxTestBase):
  """Very dumb test for privops.utils._clearLibvirtError."""
  def test(self):
    self.mox.StubOutWithMock(libvirt, 'registerErrorHandler')
    libvirt.registerErrorHandler(mox.IgnoreArg(), None)

    self.mox.ReplayAll()

    utils._clearLibvirtError()


if __name__ == '__main__':
  unittest.main()
