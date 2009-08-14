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
"""Base for debmarshal's distribution representation classes."""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import errno
import glob
import itertools
import os
import stat
import subprocess

import pkg_resources

from debmarshal import errors


def captureCall(popen_args, stdin_str=None, *args, **kwargs):
  """Capture stdout from a command.

  This method will proxy the arguments to subprocess.Popen. It returns
  the output from the command if the call succeeded and raises an
  exception if the process returns a non-0 value.

  This is intended to be a variant on the subprocess.check_call
  function that also allows you access to the output from the command.

  Args:
    popen_args: A string or sequence of program arguments. (The first
      argument to subprocess.Popen)
    stdin_str: A string to pass in on stdin. This requires the stdin
      kwarg to either be unset or subprocess.PIPE.
    All other arguments are the same as the arguments to subprocess.Popen

  Returns:
    Anything printed on stdout by the process.

  Raises:
    debmarshal.errors.CalledProcessError: Raised if the command
      returns non-0.
  """
  if 'stdin' not in kwargs:
    kwargs['stdin'] = subprocess.PIPE
  if 'stdout' not in kwargs:
    kwargs['stdout'] = subprocess.PIPE
  if 'stderr' not in kwargs:
    kwargs['stderr'] = subprocess.STDOUT
  p = subprocess.Popen(popen_args, *args, **kwargs)
  out, _ = p.communicate(stdin_str)
  if p.returncode:
    raise errors.CalledProcessError(p.returncode, popen_args, out)
  return out


def _createNewLoopDev():
  """Create a new loop device.

  On recent kernels (>2.6.22), the kernel actually supports a bunch of
  loop devices, but only creates nodes for /dev/loop0 through
  /dev/loop7 by default.

  We should be able to create more loop devices with just an
  appropriate mknod call.

  We need to try multiple times, just in case somebody else is running
  this at the same time.
  """
  while True:
    loop_nums = (int(loop[9:]) for loop in glob.glob('/dev/loop*'))
    last_loop = max(loop_nums)

    new_loop = last_loop + 1

    try:
      # TODO(ebroder): Figure out how to get udev to generate the /dev
      #   node. We want udev to be doing that so that all of the
      #   permissions get set correctly, etc.
      os.mknod('/dev/loop%d' % new_loop,
               stat.S_IFBLK | 0600,
               os.makedev(7, new_loop))
      break
    except EnvironmentError, e:
      if e.errno != errno.EEXIST:
        raise


def setupLoop(img):
  """Setup a loop device for a disk image.

  Args:
    img: Path to the image file.

  Returns:
    The image exposed as a block device.
  """
  # We have to try a few times just in case there's contention over
  # the newly created loop devices, but we also have to give up
  # eventually in case we're on an insufficiently new kernel
  for i in itertools.count(0):
    try:
      return captureCall(['losetup', '--show', '--find', img]).strip()
    except errors.CalledProcessError, e:
      if (e.output != 'losetup: could not find any free loop device\n' or
          i == 9):
        raise

      _createNewLoopDev()


def cleanupLoop(blk):
  """Clean up a loop device for a disk image.

  Args:
    blk: The block device returned from setupLoop
  """
  captureCall(['losetup', '-d', blk])


def createSparseFile(path, len):
  """Create a sparse file.

  Create a sparse file with a given length, say for use as a disk
  image.

  It is the caller's responsibility to ensure that the passed in path
  doesn't exist, or can be overwritten.

  Args:
    path: Path to the file to be created.
    len: Length of the sparse file in bytes.
  """
  dir = os.path.dirname(path)
  if not os.path.exists(dir):
    os.makedirs(dir)
  open(path, 'w').truncate(len)


def findDistribution(name):
  """Find an installed distribtion.

  Args:
    name: The name of the distribution to use. This should be the name
      of an entry_point providing debmarshal.distributions

  Returns:
    The class providing the entry_point of the given name.
  """
  entry_points = list(pkg_resources.iter_entry_points(
      'debmarshal.distributions',
      name=name))
  assert len(entry_points) == 1

  return entry_points.pop().load()
