# -*- python-indent: 2 -*-
"""tests for the debmarshal setuid support module"""

__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import os
import posix
try:
  import cStringIO as StringIO
except ImportError:
  import StringIO
import subprocess
import sys
import unittest
import mox
import yaml
from debmarshal import errors
from debmarshal import privops


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

    @privops.runWithPrivilege('test')
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
    os.stat(privops._SETUID_BINARY).AndReturn(posix.stat_result([
        # st_mode is the first argument; we don't care about anything
        # else
        0755, 0, 0, 0, 0, 0, 0, 0, 0, 0]))

    self.mox.ReplayAll()

    @privops.runWithPrivilege('test')
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
    os.stat(privops._SETUID_BINARY).AndReturn(posix.stat_result([
          # st_mode
          04755,
          0, 0, 0,
          # uid
          0,
          0, 0, 0, 0, 0]))

    self.mock_popen = self.mox.CreateMock(subprocess.Popen)
    self.mox.StubOutWithMock(subprocess, 'Popen', use_mock_anything=True)
    subprocess.Popen([privops._SETUID_BINARY,
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

    @privops.runWithPrivilege('test')
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

    @privops.runWithPrivilege('test')
    def func(*args, **kwargs):
      raise Exception('failure')

    self.assertRaises(Exception, lambda: func('a', 'b', c='d'))


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
    self.assertEqual(privops.main([]), 1)

  def testTooManyArgs(self):
    self.assertEqual(privops.main(['a', 'b', 'c', 'd']), 1)


if __name__ == '__main__':
  unittest.main()
