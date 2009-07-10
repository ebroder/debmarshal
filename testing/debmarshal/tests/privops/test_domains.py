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
"""tests for debmarshal.privops.domains."""


__authors__ = [
  'Evan Broder <ebroder@google.com>',
]


import fcntl
import os
import unittest

import libvirt
import mox

from debmarshal import errors
from debmarshal import hypervisors
from debmarshal.privops import domains
from debmarshal.privops import networks
from debmarshal.privops import utils


class TestValidateNetwork(mox.MoxTestBase):
  """Test debmarshal.privops.domains._validateNetwork."""
  networks = [('debmarshal-0', 500, '10.100.0.1'),
              ('debmarshal-1', 501, '10.100.1.1')]

  def setUp(self):
    """Use the same set of networks for all tests."""
    super(TestValidateNetwork, self).setUp()

    self.virt_con = self.mox.CreateMock(libvirt.virConnect)

    self.mox.StubOutWithMock(networks, 'loadNetworkState')
    networks.loadNetworkState(self.virt_con).AndReturn(self.networks)

  def testValidNetwork(self):
    """Valid network name from the right caller passes validation."""
    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().MultipleTimes().AndReturn(500)

    self.mox.ReplayAll()

    # Once again, we want a self.assertNoRaises, or something, but it
    # doesn't exist, so we just run the code
    domains._validateNetwork('debmarshal-0', self.virt_con)

  def testNonexistentNetwork(self):
    """Nonexistent network leads to a NetworkNotFound exception."""
    self.mox.ReplayAll()

    self.assertRaises(errors.NetworkNotFound, domains._validateNetwork,
                      'debmarshal-12', self.virt_con)

  def testWrongUser(self):
    """Wrong user leads to an AcccessDenied exception."""
    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().MultipleTimes().AndReturn(500)

    self.mox.ReplayAll()

    self.assertRaises(errors.AccessDenied, domains._validateNetwork,
                      'debmarshal-1', self.virt_con)

  def testNoConnection(self):
    """_validateNetwork is able to open its own libvirt connection."""
    self.mox.StubOutWithMock(libvirt, 'open')
    libvirt.open(mox.IgnoreArg()).AndReturn(self.virt_con)

    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().MultipleTimes().AndReturn(500)

    self.mox.ReplayAll()

    domains._validateNetwork('debmarshal-0')


class TestValidateDisk(mox.MoxTestBase):
  """Test debmarshal.privops.domains._validateDisk."""
  def setUp(self):
    """Setup the getuid/setuid dance."""
    super(TestValidateDisk, self).setUp()

    self.mox.StubOutWithMock(os, 'getuid')
    self.mox.StubOutWithMock(os, 'setuid')
    self.mox.StubOutWithMock(utils, 'getCaller')

    os.getuid().MultipleTimes().AndReturn(0)
    utils.getCaller().MultipleTimes().AndReturn(500)
    os.setuid(500)
    os.setuid(0)

  def testValidDisk(self):
    """Test access on a valid disk image."""
    self.mox.StubOutWithMock(os, 'access')

    os.access('/home/ebroder/disk.img', os.R_OK | os.W_OK).AndReturn(True)

    self.mox.ReplayAll()

    domains._validateDisk('/home/ebroder/disk.img')

  def testInvalidDisk(self):
    """Test access with an invalid disk image."""
    self.mox.StubOutWithMock(os, 'access')

    disk = '/home/not-ebroder/disk.img'
    os.access(disk, os.R_OK | os.W_OK).AndReturn(False)

    self.mox.ReplayAll()

    self.assertRaises(errors.AccessDenied, domains._validateDisk, disk)


class TestFindUnusedName(mox.MoxTestBase):
  """Test privops.domains._findUnusedName."""
  def test(self):
    virt_con = self.mox.CreateMock(libvirt.virConnect)

    self.mox.StubOutWithMock(utils, '_clearLibvirtError')
    utils._clearLibvirtError()

    name = 'debmarshal-0'
    virt_con.lookupByName(name)

    name = 'debmarshal-1'
    virt_con.lookupByName(name).AndRaise(libvirt.libvirtError(
      "Network doesn't exist"))

    self.mox.ReplayAll()

    self.assertEqual(domains._findUnusedName(virt_con), name)


class TestParseKBytes(unittest.TestCase):
  """Test privops.domains._parseKBytes."""
  def testGB(self):
    """Test amount with GB suffix."""
    self.assertEqual(domains._parseKBytes("15G"), 15728640)

  def testP(self):
    """Test amount with just 'P' for suffix."""
    self.assertEqual(domains._parseKBytes("2P"), 2199023255552)

  def testMiB(self):
    """Test amount with MiB suffix."""
    self.assertEqual(domains._parseKBytes("8MiB"), 8192)

  def testK(self):
    """Make sure that parseKBytes does the right thing with kilobytes."""
    self.assertEqual(domains._parseKBytes("12K"), 12)


class TestLoadDomainState(mox.MoxTestBase):
  """Test loading domain state from /var/run/debmarshal-domains."""
  def testAcquiringConnections(self):
    """Test acquiring libvirt connections when loading domain state.

    Also check that loadDomainState can reuse a connection it already
    has open.
    """
    doms = [('debmarshal-1', 500, 'qemu'),
            ('debmarshal-2', 500, 'qemu')]

    self.mox.StubOutWithMock(utils, '_clearLibvirtError')
    utils._clearLibvirtError()

    self.mox.StubOutWithMock(utils, 'loadState')
    utils.loadState('debmarshal-domains').AndReturn(doms)

    self.mox.StubOutWithMock(hypervisors.qemu.QEMU, 'open')
    qemu_con = self.mox.CreateMock(libvirt.virConnect)
    hypervisors.qemu.QEMU.open().AndReturn(qemu_con)

    virt_domain = self.mox.CreateMock(libvirt.virDomain)
    qemu_con.lookupByName('debmarshal-1').AndReturn(virt_domain)
    virt_domain = self.mox.CreateMock(libvirt.virDomain)
    qemu_con.lookupByName('debmarshal-2').AndReturn(virt_domain)

    self.mox.ReplayAll()

    self.assertEqual(domains.loadDomainState(), doms)

  def testNonexistentDomain(self):
    """Test that loadDomainState can deal with nonexistent domains."""
    doms = [('debmarshal-%d' % i, 500, 'qemu') for i in xrange(6)]

    self.mox.StubOutWithMock(utils, '_clearLibvirtError')
    utils._clearLibvirtError()

    self.mox.StubOutWithMock(utils, 'loadState')
    utils.loadState('debmarshal-domains').AndReturn(doms[:])

    self.mox.StubOutWithMock(hypervisors.qemu.QEMU, 'open')
    qemu_con = self.mox.CreateMock(libvirt.virConnect)
    hypervisors.qemu.QEMU.open().AndReturn(qemu_con)

    qemu_con.lookupByName('debmarshal-0')
    qemu_con.lookupByName('debmarshal-1')
    qemu_con.lookupByName('debmarshal-2').AndRaise(libvirt.libvirtError(
        "Domain doesn't exist"))
    qemu_con.lookupByName('debmarshal-3')
    qemu_con.lookupByName('debmarshal-4').AndRaise(libvirt.libvirtError(
        "Domain doesn't exist"))
    qemu_con.lookupByName('debmarshal-5')

    self.mox.ReplayAll()

    self.assertEqual(domains.loadDomainState(),
                     [doms[i] for i in [0, 1, 3, 5]])

  def testEmptyList(self):
    """Test the domain state file not existing."""
    self.mox.StubOutWithMock(utils, 'loadState')
    utils.loadState('debmarshal-domains').AndReturn(None)

    self.mox.ReplayAll()

    self.assertEqual(domains.loadDomainState(), [])


class TestCreateDomain(mox.MoxTestBase):
  """Tests for privops.domains.createNetwork."""
  def test(self):
    """Test privops.domains.createNetwork.

    With all of the functionality pulled into helper functions,
    createNetwork doesn't actually do all that much work.
    """
    name = 'debmarshal-12'
    memory = '128M'
    disks = ['/home/ebroder/root.img']
    net = 'debmarshal-0'
    mac = '00:11:22:33:44:55'

    self.mox.StubOutWithMock(os, 'geteuid')
    os.geteuid().MultipleTimes().AndReturn(0)
    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().MultipleTimes().AndReturn(500)
    self.mox.StubOutWithMock(utils, '_acquireLock')
    utils._acquireLock('debmarshal-domlist', fcntl.LOCK_EX)

    self.mox.StubOutWithMock(hypervisors.qemu.QEMU, 'open')
    qemu_con = self.mox.CreateMock(libvirt.virConnect)
    hypervisors.qemu.QEMU.open().AndReturn(qemu_con)

    self.mox.StubOutWithMock(domains, '_validateNetwork')
    domains._validateNetwork(net, qemu_con)

    self.mox.StubOutWithMock(domains, '_validateDisk')
    for d in disks:
      domains._validateDisk(d)

    self.mox.StubOutWithMock(domains, '_findUnusedName')
    domains._findUnusedName(qemu_con).AndReturn(name)

    self.mox.StubOutWithMock(hypervisors.qemu.QEMU, 'domainXMLString')
    hypervisors.qemu.QEMU.domainXMLString(mox.IgnoreArg()).AndReturn(
      '<fake_xml/>')

    self.mox.StubOutWithMock(domains, 'loadDomainState')
    domains.loadDomainState().AndReturn([
      ('debmarshal-1', 500, 'qemu')])

    self.mox.StubOutWithMock(utils, 'storeState')
    utils.storeState([
      ('debmarshal-1', 500, 'qemu'),
      (name, 500, 'qemu')], 'debmarshal-domains')

    qemu_con.createXML('<fake_xml/>', 0)

    self.mox.ReplayAll()

    self.assertEqual(domains.createDomain(
      memory, disks, net, mac), name)

if __name__ == '__main__':
  unittest.main()
