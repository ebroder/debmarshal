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
"""Information for creating Debmarshal images.

The debmarshal.distros package contains classes to control creation of
disk images for various Linux distributions (and potentially other
OSes) to use with debmarshal tests.

Because debmarshal.privops will use this package for generating disk
images, and because creating disk images is a privileged operation,
this package is trusted code.
"""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]
