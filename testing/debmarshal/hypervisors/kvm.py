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
"""KVM-specific hypervisor configuration for debmarshal"""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import libvirt
from lxml import etree

from debmarshal.hypervisors import qemu


class KVM(qemu.QEMU):
  """Hypervisor configuration specific to KVM."""
  __name__ = 'kvm'

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
    xml = super(KVM, cls).domainXML(vm)

    xml.set('type', 'kvm')

    emulator = xml.xpath('/domain/devices/emulator')[0]
    emulator.text = '/usr/bin/kvm'

    return xml
