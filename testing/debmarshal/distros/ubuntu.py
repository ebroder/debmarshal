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
"""Debmarshal distribution class for Ubuntu images."""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


from debmarshal.distros import base


class Ubuntu(base.Distribution):
  """Ubuntu (and Ubuntu-based) distributions."""
  base_defaults = {'mirror': 'http://us.archive.ubuntu.com/ubuntu/',
                   'security_mirror': 'http://security.ubuntu.com/ubuntu/',
                   'updates_mirror': 'http://us.archive.ubuntu.com/ubuntu/',
                   'backports_mirror': 'http://us.archive.ubuntu.com/ubuntu/',
                   'proposed_mirror': 'http://us.archive.ubuntu.com/ubuntu/',
                   'enable_security': True,
                   'enable_updates': True,
                   'enable_backports': False,
                   'enable_proposed': False,
                   'keyring': '/usr/share/keyrings/ubuntu-archive-keyring.gpg',
                   'arch': 'amd64',
                   'suite': 'jaunty',
                   'components': ['main', 'restricted', 'universe', 'multiverse']
                   }

  base_configurable = set(['arch', 'suite', 'components', 'enable_security',
                           'enable_updates', 'enable_backports',
                           'enable_proposed'])

  custom_defaults = {'add_pkg': [],
                     'rm_pkg': [],
                     'ssh_key': '',
                     'kernel': 'linux-image-generic',
                     # Configuration for networking doesn't really
                     # fit well into this config model. But if dhcp
                     # is True, then ip, netmask, gateway, and dns
                     # should have their default values. If dhcp is
                     # False, then they should all be set.
                     'dhcp': True,
                     'ip': None,
                     'netmask': None,
                     'gateway': None,
                     'dns': [],
                     }

  custom_configurable = set(['add_pkg', 'rm_pkg', 'ssh_key', 'kernel',
                             'hostname', 'domain',
                             'dhcp', 'ip', 'netmask', 'gateway', 'dns'])
