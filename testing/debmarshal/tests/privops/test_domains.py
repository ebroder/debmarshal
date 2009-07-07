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


import unittest

import libvirt
import mox

from debmarshal import errors
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

    self.assertRaises(errors.NetworkNotFound,
                      (lambda: domains._validateNetwork('debmarshal-12',
                                                        self.virt_con)))

  def testWrongUser(self):
    """Wrong user leads to an AcccessDenied exception."""
    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().MultipleTimes().AndReturn(500)

    self.mox.ReplayAll()

    self.assertRaises(errors.AccessDenied,
                      (lambda: domains._validateNetwork('debmarshal-1',
                                                        self.virt_con)))

  def testNoConnection(self):
    """_validateNetwork is able to open its own libvirt connection."""
    self.mox.StubOutWithMock(libvirt, 'open')
    libvirt.open(mox.IgnoreArg()).AndReturn(self.virt_con)

    self.mox.StubOutWithMock(utils, 'getCaller')
    utils.getCaller().MultipleTimes().AndReturn(500)

    self.mox.ReplayAll()

    domains._validateNetwork('debmarshal-0')


class TestFindUnusedName(mox.MoxTestBase):
  """Test privops.domains._findUnusedName."""
  def test(self):
    virt_con = self.mox.CreateMock(libvirt.virConnect)

    self.mox.StubOutWithMock(libvirt, 'registerErrorHandler')
    libvirt.registerErrorHandler(mox.IgnoreArg(), None)

    name = 'debmarshal-0'
    virt_con.lookupByName(name)

    name = 'debmarshal-1'
    virt_con.lookupByName(name).AndRaise(libvirt.libvirtError(
      "Network doesn't exist"))

    libvirt.registerErrorHandler(None, None)

    self.mox.ReplayAll()

    self.assertEqual(domains._findUnusedName(virt_con), name)


if __name__ == '__main__':
  unittest.main()
