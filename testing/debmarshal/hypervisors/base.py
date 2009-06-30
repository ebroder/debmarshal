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
"""Base for debmarshal's hypervisor representations."""


__authors__ = [
  'Evan Broder <ebroder@google.com>',
]


import os
import stat

from lxml import etree


hypervisors = {}


def _diskIsBlockDevice(disk):
  """Identify whether a particular disk is an image file or block
  device

  Args:
    disk: Path to the disk image being tested

  Returns:
    True if the disk is a block device; False if it's a file
  """
  return stat.S_ISBLK(os.stat(disk).st_mode)


class HypervisorMeta(type):
  """Metaclass to register all descendents of Hypervisor.

  When a subclass of Hypervisor is being constructed, this metaclass
  adds the new class to the hypervisors dictionary. cls.__name__ is
  used as the key, so it should be a short name to use when referring
  to the hypervisor (e.g."xen").
  """
  def __init__(cls, name, bases, d):
    super(HypervisorMeta, cls).__init__(name, bases, d)

    if '__name__' in d:
      hypervisors[d['__name__']] = cls


class Hypervisor(object):
  """Superclass representation of an abstract hypervisor used to run
  debmarshal tests.

  Classes derived from Hypervisor represent virtual machine
  hypervisors capable of creating virtual domains. They also have a
  hand in the runtime configuration of such hypervisors.
  """
  __metaclass__ = HypervisorMeta

  @staticmethod
  def domainXML(vm):
    """Generate the XML to pass to libvirt to create a new domain.

    This will generate the portions of the XML that are common to all
    hypervisors; subclasses of Hypervisor will add on elements and
    properties to the XML tree returned from their superclass.

    Args:
      vm: an instance of debmarshal.vm.VM with the parameters for the
        VM

    Returns:
      An lxml.etree.Element object containing the parsed XML tree.
    """
    xml = etree.Element('domain')
    etree.SubElement(xml, 'name').text = vm.name
    etree.SubElement(xml, 'memory').text = str(vm.memory)

    devices = etree.SubElement(xml, 'devices')
    for disk_num, disk in enumerate(vm.disks):
      xml_disk = etree.SubElement(devices, 'disk')

      if _diskIsBlockDevice(disk):
        xml_disk.set('type', 'block')
        etree.SubElement(xml_disk, 'source', dev=disk)
      else:
        xml_disk.set('type', 'file')
        etree.SubElement(xml_disk, 'source', file=disk)

      disk_letter = chr(disk_num + ord('a'))
      etree.SubElement(xml_disk, 'target', dev='sd%s' % disk_letter)

    xml_net = etree.SubElement(devices, 'interface')
    etree.SubElement(xml_net, 'source', network=vm.network)
    etree.SubElement(xml_net, 'mac', address=vm.mac)

    return xml
