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
"""tests for debmarshal.hypervisors.qemu."""


__authors__ = [
  'Evan Broder <ebroder@google.com>',
]


import os
import unittest

import libvirt
import mox

from debmarshal.hypervisors import qemu
from debmarshal import vm


class TestQEMUDomainXML(mox.MoxTestBase):
  """Test qemu.QEMU's domain XML generation."""
  def test(self):
    self.mox.StubOutWithMock(os, 'uname')
    os.uname().MultipleTimes().AndReturn((
      'Linux',
      'hostname',
      '2.6.24-24-generic',
      '#1 SMP Wed Apr 15 18:53:17 UTC 2009',
      'x86_64'))

    self.mox.ReplayAll()

    test_vm = vm.VM(name='some_name',
                    memory=42,
                    disks=[],
                    network='debmarshal-0',
                    mac='00:11:22:33:44:55')

    xml = qemu.QEMU.domainXML(test_vm)

    self.assertEqual(len(xml.xpath('/domain/os')), 1)
    self.assertEqual(len(xml.xpath('/domain/os/type')), 1)
    self.assertEqual(xml.xpath('string(/domain/os/type)'), 'hvm')
    self.assertEqual(xml.xpath('string(/domain/os/type/@arch)'), 'x86_64')

    self.assertEqual(len(xml.xpath('/domain/devices/emulator')), 1)
    self.assertEqual(xml.xpath('string(/domain/devices/emulator)'),
                     '/usr/bin/qemu-system-x86_64')


class TestQEMUOpen(mox.MoxTestBase):
  """Test that qemu.QEMU can open a connection to libvirt."""
  def test(self):
    virt_con = self.mox.CreateMock(libvirt.virConnect)

    self.mox.StubOutWithMock(libvirt, 'open')
    libvirt.open('qemu:///system').AndReturn(virt_con)

    self.mox.ReplayAll()

    self.assertEquals(qemu.QEMU.open(), virt_con)


if __name__ == '__main__':
  unittest.main()
