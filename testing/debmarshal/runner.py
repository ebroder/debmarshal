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
"""The debmarshal test runner.

This module provides the primary command-line interface to the
debmarshal testing framework.

It handles preparation of VM disk images, as well as actually
executing the test.
"""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


def _main(argv):
  """The main test runner.

  Args:
    All command line arguments.

  Returns:
    The exit code for the program.
  """
  pass


def main():
  """Run the main function with arguments from the command line."""
  sys.exit(_main(sys.argv[1:]))


if __name__ == '__main__':
  main()
