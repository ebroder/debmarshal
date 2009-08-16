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


import sys


USAGE = """Usage: debmarshal prepare [--options] [<test1> [<test2> ...]]"""


def usage():
  """Print out usage information, then error out."""
  print USAGE

  sys.exit(1)


def doPrepare(argv):
  """Prepare disk images for a series of tests.

  If no tests are specified, the current directory is assumed.

  Args:
    Command line arguments after the subcommand.

  Returns:
    The exit code for this subcommand.
  """
  pass


def _main(argv):
  """The main test runner. Dispatcher to subcommands.

  Args:
    All command line arguments.

  Returns:
    The exit code for the program.
  """
  if argv[0] == 'prepare':
    return doPrepare(argv[1:])
  else:
    usage()


def main():
  """Run the main function with arguments from the command line."""
  sys.exit(_main(sys.argv[1:]))


if __name__ == '__main__':
  main()
