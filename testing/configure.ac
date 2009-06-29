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
#
# Author: Evan Broder <ebroder@google.com>

AC_INIT([setup.py], 0.0.0)
AM_INIT_AUTOMAKE([foreign])

AC_PROG_CC
AM_PATH_PYTHON
AC_DEFINE_UNQUOTED([PYTHON], ["$PYTHON"], [Path to Python interpreter])

AC_CONFIG_HEADERS([config.h])
AC_CONFIG_FILES([Makefile debmarshal/config.py])
AC_OUTPUT
