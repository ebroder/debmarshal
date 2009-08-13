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
import debmarshal.utils
from debmarshal._privops import utils


class TestCoerceDbusType(unittest.TestCase):
  """Test for privops.utils.coerceDbusType."""
  def testInts(self):
    self.assertEqual(utils.coerceDbusType(dbus.Byte(12)), 12)
    self.assertEqual(utils.coerceDbusType(dbus.Int16(12)), 12)
    self.assertEqual(utils.coerceDbusType(dbus.Int32(12)), 12)
    self.assertEqual(utils.coerceDbusType(dbus.UInt16(12)), 12)
    self.assertEqual(utils.coerceDbusType(dbus.UInt32(12)), 12)

  def testDouble(self):
    self.assertEqual(utils.coerceDbusType(dbus.Double(12.3)), 12.3)

  def testBoolean(self):
    self.assertEqual(utils.coerceDbusType(dbus.Boolean(0)), False)
    self.assertEqual(utils.coerceDbusType(dbus.Boolean(1)), True)

  def testStrings(self):
    self.assertEqual(utils.coerceDbusType(dbus.UTF8String("blah")), "blah")
    self.assertEqual(utils.coerceDbusType(dbus.ByteArray(u"blah")), "blah")
    self.assertEqual(utils.coerceDbusType(dbus.String(u"blah")), u"blah")
    self.assertEqual(utils.coerceDbusType(dbus.Signature(u"ssi")), u"ssi")
    self.assertEqual(utils.coerceDbusType(dbus.ObjectPath(
        u"/com/googlecode/debmarshal/Privops")), u"/com/googlecode/debmarshal/Privops")

  def testCollections(self):
    self.assertEqual(
        utils.coerceDbusType(dbus.Struct((
            dbus.String('x'), dbus.String('y'), dbus.String('z')))),
        ('x', 'y', 'z'))

    self.assertEqual(
        utils.coerceDbusType(dbus.Array([
            dbus.Int16(12), dbus.Int16(13), dbus.Int16(14)])),
        [12, 13, 14])

    self.assertEqual(
        utils.coerceDbusType(dbus.Dictionary({
            dbus.Int16(12): dbus.String('foo'),
            dbus.Int16(13): dbus.String('bar')})),
        {12: 'foo', 13: 'bar'})

  def testPythonType(self):
    obj = object()
    self.assertEqual(utils.coerceDbusType(obj), obj)


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

    self.mox.StubOutWithMock(dbus, 'SystemBus', use_mock_anything=True)

    dbus.SystemBus().AndReturn(bus)
    bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus').AndReturn(
        dbus_obj)
    dbus_obj.GetConnectionUnixUser(
        utils.caller, dbus_interface='org.freedesktop.DBus').\
        AndReturn(dbus.UInt32(uid))

    self.mox.ReplayAll()

    self.assertEquals(utils.getCaller(), uid)

    utils.caller = None


class TestLoadState(mox.MoxTestBase):
  """Test loading state from /var/run."""
  def setUp(self):
    """Stub out acquiring the lock."""
    super(TestLoadState, self).setUp()

    lock_file = self.mox.CreateMock(file)
    self.mox.StubOutWithMock(debmarshal.utils, 'acquireLock')
    debmarshal.utils.acquireLock('debmarshal-networks', fcntl.LOCK_SH).\
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
    self.mox.StubOutWithMock(debmarshal.utils, 'acquireLock')
    debmarshal.utils.acquireLock('debmarshal-networks', fcntl.LOCK_EX).\
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
