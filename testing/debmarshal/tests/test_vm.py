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
"""Tests for debmarshal.vm."""


__authors__ = [
  'Evan Broder <ebroder@google.com>',
]


import unittest

from debmarshal import errors
from debmarshal import vm


class TestVM(unittest.TestCase):
  """Test the debmarshal.vm.VM class."""
  def testGoodArguments(self):
    """Make sure that debmarshal.vm.VM.__init__ succeeds if memory,
    disks, and network are passed in.

    There's not a good way to assert that a call doesn't raise an
    exception, so the best we can do is call the function, and if it
    does raise an exception, then the test ends with an error. Not
    quite as good as ending with a failure, but it'll have to do.
    """
    vm.VM(name='debmarshal-12',
          memory=524288,
          disks=['/home/ebroder/root.img',
                 '/home/ebroder/swap.img'],
          network='debmarshal-0',
          mac='AA:BB:CC:DD:EE:FF')

  def testMissingArguments(self):
    """Make sure that vm.VM's __init__ raises an exception if all
    expected arguments aren't passed in."""
    self.assertRaises(errors.InvalidInput, vm.VM)

  def testExtraArguments(self):
    """Make sure that an exception is raised if vm.VM.__init__ gets
    too many arguments."""
    self.assertRaises(errors.InvalidInput, vm.VM,
                      name='debmarshal-12',
                      memory=524288,
                      disks=['/home/ebroder/root.img'],
                      network='debmarshal-0',
                      mac='AA:BB:CC:DD:EE:FF',
                      foo='bar')


if __name__ == '__main__':
  unittest.main()
