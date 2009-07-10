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
"""Tests for debmarshal.ip."""


__authors__ = [
  'Evan Broder <ebroder@google.com>',
]


import unittest

from debmarshal import ip


class TestArithmeticMixin(unittest.TestCase):
  """Test the debmarshal.ip.ArithmeticMixin class."""
  def testAdd(self):
    """Test adding classes with the ArithmeticMixin."""
    self.assertEqual(ip.IPv4('192.168.1.1') + 1, ip.IPv4('192.168.1.2'))

  def testSub(self):
    """Test subtracting classes with the ArithmeticMixin."""
    self.assertEqual(ip.IPv4('192.168.1.2') - 1, ip.IPv4('192.168.1.1'))


class TestIP(unittest.TestCase):
  """Test the debmarshal.ip.IP function.

  This uses tests from the upstream ipaddr test module.
  """
  def test(self):
    ipv4 = ip.IP('1.2.3.4')
    ipv6 = ip.IP('::1.2.3.4')
    self.assertEquals(ip.IPv4, type(ipv4))
    self.assertEquals(ip.IPv6, type(ipv6))

    self.assertRaises(ValueError, ip.IP, 'google.com')


if __name__ == '__main__':
  unittest.main()
