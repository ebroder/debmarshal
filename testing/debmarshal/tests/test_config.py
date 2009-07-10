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
"""Tests for debmarshal.config."""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import unittest

from debmarshal import config


class TestEvalVariable(unittest.TestCase):
  """Test evaluating variable expressions within the config module."""
  def test(self):
    config.foo = 'bar'

    self.assertEqual(config.evalVariable('${foo}'), 'bar')


if __name__ == '__main__':
  unittest.main()
