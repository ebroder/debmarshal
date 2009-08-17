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

import libvirt
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
      An lxml.etree.Element object containing the XML to specify the
        domain
    """
    xml = super(QEMU, cls).domainXML(vm)

    xml.set('type', 'qemu')

    xml_os = xml.xpath('/domain/os')[0]
    etree.SubElement(xml_os, 'type', arch=vm.arch).text = 'hvm'

    xml_devices = xml.xpath('/domain/devices')[0]

    etree.SubElement(xml_devices, 'graphics', type='vnc')

    emulator = etree.SubElement(xml_devices, 'emulator')
    emulator.text = '/usr/bin/qemu-system-%s' % vm.arch

    return xml

  @staticmethod
  def open():
    """Open a read-write libvirt connection to the qemu hypervisor.

    Returns:
      A read-write libvirt.virConncect connection to qemu
    """
    return libvirt.open('qemu:///system')

  @staticmethod
  def openReadOnly():
    """Open a read-only libvirt connection to the qemu hypervisor.

    Returns:
      A read-only libvirt.virConnect connection to qemu.
    """
    return libvirt.openReadOnly('qemu:///system')
