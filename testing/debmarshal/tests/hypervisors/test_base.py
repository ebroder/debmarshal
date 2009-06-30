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
"""tests for debmarshal.hypervisors.base."""

__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import os
import posix
import unittest

import mox

from debmarshal.hypervisors import base
from debmarshal import vm


class TestDiskIsBlockDevice(mox.MoxTestBase):
  """Test base._diskIsBlockDevice."""
  def testBlockDevice(self):
    self.mox.StubOutWithMock(os, 'stat')
    os.stat('/home/ebroder/root.img').AndReturn(posix.stat_result([
      # st_mode is the first argument
      060644, 0, 0, 0, 0, 0, 0, 0, 0, 0]))

    self.mox.ReplayAll()

    self.assertEqual(base._diskIsBlockDevice('/home/ebroder/root.img'),
                     True)

  def testFile(self):
    self.mox.StubOutWithMock(os, 'stat')
    os.stat('/home/ebroder/root.img').AndReturn(posix.stat_result([
      0100644, 0, 0, 0, 0, 0, 0, 0, 0, 0]))

    self.mox.ReplayAll()

    self.assertEqual(base._diskIsBlockDevice('/home/ebroder/root.img'),
                     False)


class TestHypervisorDomainXML(mox.MoxTestBase):
  """Test base.Hypervisor.domainXML."""
  def testNoDisks(self):
    """Generate XML from a VM with no disks to probe the other pieces
    of the resulting XML."""
    test_vm = vm.VM(name='some_name',
                    memory=42,
                    disks=[],
                    network='debmarshal-0',
                    mac='00:11:22:33:44:55')

    xml = base.Hypervisor.domainXML(test_vm)

    # First, is the root element <domain/>?
    self.assertNotEqual(xml.xpath('/domain'), [])

    # Is there one of each of <name/> and <memory/>? Are they right?
    self.assertEqual(len(xml.xpath('/domain/name')), 1)
    self.assertEqual(xml.xpath('string(/domain/name)'), test_vm.name)
    self.assertEqual(len(xml.xpath('/domain/memory')), 1)
    self.assertEqual(xml.xpath('string(/domain/memory)'), str(test_vm.memory))

    # And did the networking get setup right?
    self.assertEqual(len(xml.xpath('/domain/devices/interface')), 1)
    self.assertEqual(len(xml.xpath('/domain/devices/interface/source')), 1)
    self.assertEqual(len(xml.xpath('/domain/devices/interface/mac')), 1)

    net_attr = 'string(/domain/devices/interface/%s)'
    self.assertEqual(xml.xpath(net_attr % 'source/@network'),
                     test_vm.network)
    self.assertEqual(xml.xpath(net_attr % 'mac/@address'),
                     test_vm.mac)


if __name__ == '__main__':
  unittest.main()
