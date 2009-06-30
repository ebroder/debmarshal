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
"""QEMU-specific hypervisor configuration for debmarshal"""


__authors__ = [
  'Evan Broder <ebroder@google.com>',
]


import os

from lxml import etree

from debmarshal.hypervisors import base


class QEMU(base.Hypervisor):
  """Hypervisor configuration specific to QEMU."""
  __name__ = 'qemu'

  @classmethod
  def domainXML(cls, vm):
    """Generate the XML to pass to libvirt to create a new domain.

    Args:
      vm: an instance of debmarshal.vm.VM with the parmaeters for the
        VM to create

    Returns:
      An lxml.etree Element object with the parsed XML tree.
    """
    # TODO(ebroder): Take advantage of qemu's cross-architecture
    #   support to let us specify the architecture/bittedness/etc of
    #   the guest
    xml = super(QEMU, cls).domainXML(vm)

    # `uname -m` returns the architecture of the kernel, which may not
    # be the same as the architecture of the userspace.
    #
    # It's not really clear which architecture is the best default, so
    # we're just going to use the one that's easiest to get to.
    host_arch = os.uname()[4]

    xml_os = etree.SubElement(xml, 'os')
    etree.SubElement(xml_os, 'type', arch=host_arch).text = 'hvm'

    xml_devices = xml.xpath('/domain/devices')[0]

    emulator = etree.SubElement(xml_devices, 'emulator')
    emulator.text = '/usr/bin/qemu-system-%s' % host_arch

    return xml
