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
"""tests for debmarshal.privops.utils"""


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
import posix
try:
  import cStringIO as StringIO
except ImportError:
  import StringIO
import subprocess
import sys
import unittest

import libvirt
import mox
import yaml

from debmarshal import errors
from debmarshal.privops import utils


class TestRunWithPrivilege(mox.MoxTestBase):
  """Testing runWithPrivilege before it actually executes anything"""
  def testFunctionCalledDirectlyAsRoot(self):
    """Test that functions wrapped in runWithPrivilege are executed
    directly if you're already root.
    """
    self.mox.StubOutWithMock(os, 'geteuid')
    os.geteuid().AndReturn(0)

    # We want to make sure that runWithPrivilege doesn't try to
    # re-execute itself through the setuid wrapper.
    #
    # By stubbing out os.stat without actually recording any calls to
    # it, we can trigger an error of runWithPrivilege starts trying to
    # re-execute itself.
    self.mox.StubOutWithMock(os, 'stat')
    self.mox.StubOutWithMock(subprocess, 'Popen')

    self.mox.ReplayAll()

    @utils.runWithPrivilege('test')
    def func():
      # Stupid function - all we care about is that it gets run
      return 1

    self.assertEqual(func(), 1)

  def testAbortIfWrapperNotSetuid(self):
    """Test that if you're not root, and the setuid wrapper isn't
    setuid, runWithPrivileges aborts.
    """
    self.mox.StubOutWithMock(os, 'geteuid')
    os.geteuid().AndReturn(1000)

    self.mox.StubOutWithMock(os, 'stat')
    os.stat(utils._SETUID_BINARY).AndReturn(posix.stat_result([
        # st_mode is the first argument; we don't care about anything
        # else
        0755, 0, 0, 0, 0, 0, 0, 0, 0, 0]))

    self.mox.ReplayAll()

    @utils.runWithPrivilege('test')
    def func():
      self.fail('This function should never have been run.')

    self.assertRaises(errors.Error, func)


class TestReexecResults(mox.MoxTestBase):
  """Test the actual process of execing the setuid wrapper.

  This requires some substantial mocking of both the os module and
  subprocess.Popen.
  """
  def setUp(self):
    """Setup mocks through the point of actually forking and execing.

    This involves faking a binary that's setuid, as well as faking
    actually running it.
    """
    super(TestReexecResults, self).setUp()

    self.mox.StubOutWithMock(os, 'geteuid')
    os.geteuid().AndReturn(1000)

    self.mox.StubOutWithMock(os, 'stat')
    os.stat(utils._SETUID_BINARY).AndReturn(posix.stat_result([
          # st_mode
          04755,
          0, 0, 0,
          # uid
          0,
          0, 0, 0, 0, 0]))

    self.mock_popen = self.mox.CreateMock(subprocess.Popen)
    self.mox.StubOutWithMock(subprocess, 'Popen', use_mock_anything=True)
    subprocess.Popen([utils._SETUID_BINARY,
                      'test',
                      mox.Func(lambda x: yaml.safe_load(x) == ['a', 'b']),
                      mox.Func(lambda x: yaml.safe_load(x) == {'c': 'd'})],
                     stdin=None,
                     stdout=subprocess.PIPE,
                     close_fds=True).AndReturn(self.mock_popen)

  def testReexecSuccessResult(self):
    """Verify that the printout from runWithPrivileges is treated as a
    return value if the program exits with a return code of 0.
    """
    self.mock_popen.wait().AndReturn(0)
    self.mock_popen.stdout = StringIO.StringIO(yaml.dump('foo'))

    self.mox.ReplayAll()

    @utils.runWithPrivilege('test')
    def func(*args, **kwargs):
      return 'foo'

    self.assertEquals(func('a', 'b', c='d'), 'foo')

  def testReexecFailureResult(self):
    """Verify that the printout from runWithPrivileges is treated as
    an exception if the program exits with a return code of 1.
    """
    self.mock_popen.wait().AndReturn(1)
    self.mock_popen.stdout = StringIO.StringIO(yaml.dump(Exception('failure')))

    self.mox.ReplayAll()

    @utils.runWithPrivilege('test')
    def func(*args, **kwargs):
      raise Exception('failure')

    self.assertRaises(Exception, func, 'a', 'b', c='d')


class TestGetCaller(mox.MoxTestBase):
  """Test for privops.utils.getCaller"""
  def test(self):
    """Verify that privops.utils.getCaller returns os.getuid.

    This is sort of a dumb test, but at least it'll start failing if
    we change the mechanisms by which debmarshal escalates privileges,
    and then we can come up with a better test.
    """
    self.mox.StubOutWithMock(os, 'getuid')
    os.getuid().AndReturn(42)

    self.mox.ReplayAll()

    self.assertEquals(utils.getCaller(), 42)


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
  """Test debmarshal.privops.utils.storeState."""
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


class TestUsage(mox.MoxTestBase):
  """Make sure that usage information gets printed"""
  def setUp(self):
    """Record printing out something that looks like usage information.

    We'll try to trigger it a bunch of different ways.
    """
    super(TestUsage, self).setUp()

    self.mox.StubOutWithMock(sys, 'stderr')
    sys.stderr.write(mox.StrContains('Usage'))
    sys.stderr.write(mox.IgnoreArg()).MultipleTimes()

    self.mox.ReplayAll()

  def testNoArgs(self):
    """Trigger usage information by passing in no arguments"""
    self.assertEqual(utils.main([]), 1)

  def testTooManyArgs(self):
    """Trigger usage information by passing in too many arguments"""
    self.assertEqual(utils.main(['a', 'b', 'c', 'd']), 1)


class TestMain(mox.MoxTestBase):
  """Test argument and return parsing in main"""
  def testSuccess(self):
    """Test that the return value is printed to stdout and that the
    return code is 0 if the function returns
    """
    self.mox.StubOutWithMock(sys, 'stdout')
    print >>sys.stdout, yaml.dump('success')

    self.mox.ReplayAll()

    args = ('foo', {'bar': 'quux'})
    kwargs = {'spam': 'eggs'}

    def test_args(*input_args, **input_kwargs):
      self.assertEqual(args, input_args)
      self.assertEqual(kwargs, input_kwargs)
      return 'success'
    utils._subcommands['test'] = test_args

    self.assertEqual(utils.main([
          'test', yaml.safe_dump(args), yaml.safe_dump(kwargs)]), 0)

  def testFailure(self):
    """Test that the exception is printed to stdout and that the
    return code is 1 if the function raises one
    """
    self.mox.StubOutWithMock(sys, 'stdout')
    print >>sys.stdout, yaml.dump(Exception('failure'))

    self.mox.ReplayAll()

    def test():
      raise Exception('failure')
    utils._subcommands['test'] = test

    self.assertEqual(utils.main([
          'test', yaml.safe_dump([]), yaml.safe_dump({})]), 1)


if __name__ == '__main__':
  unittest.main()
