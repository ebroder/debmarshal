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
"""Create an Ubuntu image as an unprivileged user."""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


def genCommandLine(preseed):
  """Given a preseed file, generate a list of command line args.

  If the preseed file has some number of blocks starting with "###
  BEGIN COMMAND LINE ARGS" and ending with "### END COMMAND LINE
  ARGS", those Debconf options will be extracted and reformatted as
  part of the kernel command line.

  This function is not your mother; if your preseed file forgets the
  closing block, we won't tell you, and the behavior of the function
  is not well-defined.

  It's also your problem to be sure that none of the options to be
  passed in on the command line contain spaces, because the kernel
  isn't clever enough to deal with them.

  Args:
    preseed: Path to a Debconf preseed file.

  Returns:
    A string containing the arguments to pass on the kernel command
      line.
  """
  args = {}
  capturing_args = False
  for line in open(preseed):
    if line == '### BEGIN COMMAND LINE ARGS\n':
      capturing_args = True
    elif line == '### END COMMAND LINE ARGS\n':
      capturing_args = False

    if capturing_args and not line.lstrip().startswith('#'):
      opt, _, value = line.split()[1:5]
      args[opt] = value

  return ' '.join('%s=%s' % (k, v) for k, v in args.iteritems())
