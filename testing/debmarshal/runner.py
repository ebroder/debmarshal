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


import optparse
import os
import sys


USAGE = """Usage: debmarshal prepare [--options] [<test1> [<test2> ...]]"""


def usage():
  """Print out usage information, then error out."""
  print USAGE

  sys.exit(1)


def parsePrepareArgs(argv):
  """Parse command line options for the prepare subcommand.

  Args:
    argv: A list of all command line arguments after the subcommand.

  Returns:
    A 2-tuple of (options, arguments), where options is an object
      containing all options.
  """
  parser = optparse.OptionParser()
  # We don't actually have any options to parse yet, but they'll go
  # here if we ever do.

  return parser.parse_args(argv)


def prepareTest(test):
  """Prepare the disk image for a single test.

  Args:
    Path to a debmarshal test.
  """
  pass


def doPrepare(argv):
  """Prepare disk images for a series of tests.

  If no tests are specified, the current directory is assumed.

  Args:
    Command line arguments after the subcommand.

  Returns:
    The exit code for this subcommand.
  """
  opts, args = parsePrepareArgs(argv)

  if not args:
    args = [os.getcwd()]

  for test in args:
    prepareTest(test)


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
