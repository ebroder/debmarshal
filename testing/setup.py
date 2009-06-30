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
from setuptools import setup, find_packages

setup(name="debmarshal",
      version="0.0.0",
      description="Virtualization-based testing framework",
      author="Evan Broder",
      author_email="ebroder@google.com",
      url="http://code.google.com/p/debmarshal/",
      packages=find_packages(),
      long_description="""
The Debmarshal testing framework is designed to make it easy to test
entire systems and interactions between multiple systems. It uses
libvirt and other virtualization techniques to build entire platforms
for running automated tests in an environment isolated from the
outside world.
""",
      requires=['decorator', 'PyYAML', 'ipaddr'],
      setup_requires=['nose>=0.9.2'],
      test_suite = 'nose.collector',
      tests_require=['mox'],
      dependency_links=['http://code.google.com/p/pymox/downloads/list',
                        'http://code.google.com/p/ipaddr-py/downloads/list']
)
