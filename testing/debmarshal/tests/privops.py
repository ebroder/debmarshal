# -*- python-indent: 2 -*-
"""tests for the debmarshal setuid support module"""

__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import os
import subprocess
import sys
import unittest
import mox
from debmarshal import privops


class TestRunWithPrivilege(mox.MoxTestBase):
  def testFunctionCalledDirectlyAsRoot(self):
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


if __name__ == '__main__':
  unittest.main()
