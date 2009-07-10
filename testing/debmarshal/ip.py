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
"""debmarshal extensions to the ipaddr module."""

__authors__ = [
  'Evan Broder <ebroder@google.com>',
]


import ipaddr


class ArithmeticMixin(object):
  """A mixin class for adding arithmetic support to other classes.

  Classes that subclass ArithmeticMixin, have a __int__ method, and
  can accept the output from that method as an argument to __init__
  have support for simple arithmetic added to them.
  """

  def __add__(self, y):
    return self.__class__(int(self) + y)

  def __sub__(self, y):
    return self.__class__(int(self) - y)


class IPv4(ipaddr.IPv4, ArithmeticMixin):
  __doc__ = ipaddr.IPv4.__doc__


class IPv6(ipaddr.IPv6, ArithmeticMixin):
  __doc__ = ipaddr.IPv6.__doc__

def IP(addr):
  """Take an IP string/int and return an object of the correct type.

  Args:
    addr: A string or integer, the IP address.  Either IPv4 or
      IPv6 addresses may be supplied; integers less than 2**32 will
      be considered to be IPv4.

  Returns:
    An IPv4 or IPv6 object.

  Raises:
    ValueError: if the string passed isn't either a v4 or a v6
    address.
  """

  try:
    return IPv4(addr)
  except (ipaddr.IPv4IpValidationError, ipaddr.IPv4NetmaskValidationError):
    pass

  try:
    return IPv6(addr)
  except (ipaddr.IPv6IpValidationError, ipaddr.IPv6NetmaskValidationError):
    pass

  raise ValueError('%r does not appear to be an IPv4 or IPv6 address' %
                   addr)
