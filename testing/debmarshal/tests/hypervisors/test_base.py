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


import unittest

from lxml import etree
import mox

from debmarshal import errors
from debmarshal.hypervisors import base
from debmarshal import utils
from debmarshal import vm


class TestHypervisorMeta(unittest.TestCase):
  """Test the base.HypervisorMeta metaclass."""
  def testWithoutName(self):
    """Test that Hypervisor-descended classes without a __name__
    attribute don't end up in base.hypervisors."""
    class NamelessMetaTest(base.Hypervisor):
      pass

    self.assert_(NamelessMetaTest not in base.hypervisors.values())

  def testWithName(self):
    """Test that Hypervisor-descended classes with a __name__
    attribute do show up in base.hypervisors."""
    class NamedMetaTest(base.Hypervisor):
      __name__ = 'test'

    self.assertEqual(NamedMetaTest, base.hypervisors['test'])

  def testNoHypervisor(self):
    """Test that Hypervisor itself isn't in base.hypervisors."""
    self.assert_(base.Hypervisor not in base.hypervisors.values())


class TestHypervisorDomainXML(mox.MoxTestBase):
  """Test base.Hypervisor.domainXML."""
  def testNoDisks(self):
    """Generate XML from a VM with no disks to probe the other pieces
    of the resulting XML."""
    test_vm = vm.VM(name='some_name',
                    memory=42,
                    disks=[],
                    network='debmarshal-0',
                    mac='00:11:22:33:44:55',
                    arch='x86_64')

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
    self.assertEqual(xml.xpath(net_attr % '@type'),
                     'network')
    self.assertEqual(xml.xpath(net_attr % 'source/@network'),
                     test_vm.network)
    self.assertEqual(xml.xpath(net_attr % 'mac/@address'),
                     test_vm.mac)

  def testDisks(self):
    """Generate XML from a VM and verify the disk specifications"""
    test_vm = vm.VM(name='something',
                    memory=1000000000,
                    disks=['/home/ebroder/block-dev',
                           '/home/ebroder/file.img'],
                    network='debmarshal-1',
                    mac='AA:BB:CC:DD:EE:FF',
                    arch='x86_64')

    self.mox.StubOutWithMock(utils, 'diskIsBlockDevice')
    utils.diskIsBlockDevice('/home/ebroder/block-dev').AndReturn(True)
    utils.diskIsBlockDevice('/home/ebroder/file.img').AndReturn(False)

    self.mox.ReplayAll()

    xml = base.Hypervisor.domainXML(test_vm)

    self.assertEqual(len(xml.xpath('/domain/devices/disk')), 2)
    disk = xml.xpath('/domain/devices/disk[target/@dev="hda"]')[0]
    self.assertEqual(disk.xpath('string(@type)'), 'block')
    self.assertEqual(len(disk.xpath('source')), 1)
    self.assertEqual(disk.xpath('string(source/@dev)'), test_vm.disks[0])

    disk = xml.xpath('/domain/devices/disk[target/@dev="hdb"]')[0]
    self.assertEqual(len(disk.xpath('source')), 1)
    self.assertEqual(disk.xpath('string(@type)'), 'file')
    self.assertEqual(len(disk.xpath('source')), 1)
    self.assertEqual(disk.xpath('string(source/@file)'), test_vm.disks[1])


class TestDomainXMLString(mox.MoxTestBase):
  """Test hypervisors.base.Hypervisor.domainXMLString."""
  def test(self):
    self.mox.StubOutWithMock(base.Hypervisor, 'domainXML')
    xml = etree.Element('some_element')
    base.Hypervisor.domainXML(mox.IgnoreArg()).AndReturn(xml)

    self.mox.ReplayAll()

    self.assertEqual(base.Hypervisor.domainXMLString(None), etree.tostring(xml))


class TestHypervisorOpen(unittest.TestCase):
  """Dumb test for Hypervisor.open"""
  def test(self):
    self.assertRaises(errors.NotImplementedError, base.Hypervisor.open)


if __name__ == '__main__':
  unittest.main()
