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
"""Representations of virtual machines used in debmarshal tests."""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


from debmarshal import errors


class VM(object):
  """A virtual machine representation.

  This is basically used as a glorified struct for passing parameters
  around.

  Attributes:
    name: The name of the domain, as known to libvirt.
    memory: How much RAM this VM is supposed to be allocated, in
      (binary) kilobytes.
    disks: list of strs of paths to disk images, in the order that
      they should be attached to the guest.
    network: Which debmarshal-managed network to attach this VM to.
    mac: The MAC address of the VM's network interface.
  """
  __slots__ = ['name', 'memory', 'disks', 'network', 'mac']

  def __init__(self, **kwargs):
    """Initialize a VM object.

    Args:
      kwargs: All public attributes of the VM should be passed in as
        keyword arguments

    Raises:
      debmarshal.errors.InvalidInput if any additional arguments past
        the public attributes of a VM object are passed in, or if any
        expected arguments are missing.
    """
    for var in self.__slots__:
      if var not in kwargs:
        raise errors.InvalidInput(
            'Expected argument "%s" to VM.__init__ missing' % var)
      setattr(self, var, kwargs.pop(var))

    if kwargs:
      raise errors.InvalidInput('Extra arguments passed to VM.__init__')
