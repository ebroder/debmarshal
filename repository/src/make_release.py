#!/usr/bin/python2.4
#
# Copyright 2006 Google Inc.
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

"""Script to define and to publish releases

The make_release.py script is a repository-administrator command for
defining, inspecting, verifying, and publishing releases.  Basically
the administrator defines a release as a list of binary packages by
referring to various sources, and the make_release.py takes care of
the rest of the work.
"""

__author__ = 'cklin@google.com (Chuan-Kai Lin)'

import logging as lg
import optparse
import os
import sys
import alias_utils as au
import bsddb_utils as bu
import deb_utils as du
import logging_utils as lu
import os_utils as ou
import release_utils as ru
import setting_utils as su
import verifier_utils as vu


def _ParseCommandLine():
  """Parse and check command line options and arguments

  This function uses the optparse module to parse the command line
  options, and it then checks that the command line arguments are
  well-formed in accordance with the semantics of the script.
  """

  usage = 'usage: %prog [options] [diff RELEASE | commit]'
  version = 'Debmarshall 0.0'
  parser = optparse.OptionParser(usage=usage, version=version)

  parser.add_option('-s', '--snapshot',
                    dest='snapshot', action='store_true',
                    help='include latest packages in the pool')
  parser.add_option('-d', '--dist',
                    dest='dist', metavar='PATH', action='append',
                    help='base new release on Packages files in PATH')
  parser.add_option('-i', '--import',
                    dest='imp', metavar='FILE', action='append',
                    help='use name_ver_arch strings in FILE')
  parser.add_option('-r', '--release',
                    dest='release', metavar='RELEASE', action='append',
                    help='base new release on RELEASE')
  parser.add_option('-t', '--track',
                    dest='track', metavar='TRACK',
                    help='prepare release for TRACK')

  options, proper = parser.parse_args()
  if not (options.release or options.dist or
          options.snapshot or options.imp):
    lg.error('At least one of -s, -d, -r, -i should be issued.')
    sys.exit()

  if len(proper) != 0:
    if proper[0] == 'commit':
      if len(proper) != 1:
        lg.error('commit command requires no arguments')
        sys.exit()
      elif not options.track:
        lg.error('commit command depends on the -t option')
        sys.exit()
    elif proper[0] == 'diff':
      if len(proper) != 2:
        lg.error('diff command requires an argument')
        sys.exit()
    elif proper[0] == 'rebuild':
      if len(proper) != 1:
        lg.error('rebuild command requires no arguments')
        sys.exit()
      elif (not options.release or len(options.release) != 1 or
            options.dist or options.snapshot or
            options.imp or options.track):
        lg.error('rebuild command requires one -r option only')
        sys.exit()
    elif proper[0] == 'verify':
      if len(proper) != 1:
        lg.error('verify command requires no arguments')
        sys.exit()
    else:
        lg.error(proper[0] + ' is not a legal command')
        sys.exit()

  return options, proper


def main():
  lu.SetLogConsole()
  options, proper = _ParseCommandLine()

  def DoSnapshot(_arg, dbs):
    return ru.SelectLatestPackages(dbs['pkg_info'])

  def DoRetrieve(release, dbs):
    releases = dbs['releases']
    aliases = dbs['aliases']
    return ru.FetchReleaseList(release, releases, aliases)[0]

  def DoImport(lines):
    p = []
    for line in lines:
      p.append(line.rstrip('\n'))
    return p

  def DoCollect(_arg, dbs):
    return ru.CollectPackageVersions(dbs['pkg_info'])

  def DoVerify(nva_list, dbs):
    pkg_deps = du.ParseDependencyTable(dbs['pkg_deps'])
    return ru.CollectSources(nva_list, pkg_deps, dbs['src_info'])

  if options.track:
    su.ConfirmTrack(options.track)

  packages = []

  # Add latest packages from the Berkeley DB tables.

  if options.snapshot:
    packages.extend(bu.RunWithDB(['pkg_info'], DoSnapshot))

  # Add packages in Packages files in a dists/ subtree.

  if options.dist is not None:
    for dist in options.dist:
      packages.extend(ru.GetUpstreamReleaseList(dist))

  # Add packages listed in a text file.

  if options.imp is not None:
    for imp in options.imp:
      packages.extend(ou.RunWithFileInput(DoImport, imp))

  # Add packages in an existing release.

  if options.release is not None:
    for release in options.release:
      db_list = ['releases', 'aliases']
      result = bu.RunWithDB(db_list, DoRetrieve, release)
      packages.extend(result)

  # Version selection: work through the list to determine which
  # version of each package should be included in the release.

  ver_dict = bu.RunWithDB(['pkg_info'], DoCollect, None)
  packages = ru.SelectLatestPackages(packages)
  ver_dict = ru.CutOffVersions(ver_dict, packages)
  if options.track:
    name = os.path.join('config', options.track + '.spec')
    ver_dict = ru.FilterVersionWithFile(ver_dict, name)

  # Convert results of version selection back to an nva list.

  packages = []
  for n, a in ver_dict:
    if not ver_dict[(n, a)]:  continue
    packages.append('_'.join([n, ver_dict[(n, a)][0], a]))
  packages.sort()

  if len(proper) != 0:

    # Publish the release and write records into Berkeley DB tables.

    if proper[0] == 'commit':
      ru.GenerateReleaseList(options.track, packages)

    # Compare binary package list with an existing release.

    if proper[0] == 'diff':
      rel = proper[1]
      db_list = ['releases', 'aliases']
      cf = bu.RunWithDB(db_list, DoRetrieve, rel)
      old_dict = dict.fromkeys(cf)
      new_dict = dict.fromkeys(packages)
      print 'Packages discarded from', rel + ':'
      for p in sorted(cf):
        if p not in new_dict:
          print '-', p
      print
      print 'Packages added to the new release:'
      for p in packages:
        if p not in old_dict:
          print '+', p

    # Republish a previously-defined release.

    if proper[0] == 'rebuild':
      [track, ver] = options.release[0].split('/')
      ru.GenerateReleaseVersion(track, ver)

    # Perform release consistency checking.

    if proper[0] == 'verify':
      underlying = []
      bases = su.GetSetting(options.track, 'Underlying')
      if bases:

        # Build the underlying package list and import underlying
        # dependency databases when necessary

        for base in bases.split(', '):
          base_list = base.split(' ', 1)
          if len(base_list) != 2:
            lg.error('malformed underlying release ' + base)
            continue
          base_url = base_list[0]
          base_rel = base_list[1]
          base_packages = bu.FetchUnderlyingRelease(base_url, base_rel)
          bu.ImportUnderlyingTables(base_url, base_packages)
          underlying.extend(base_packages)

        # Select only the latest packages in either packages (release
        # to be verified) or underlying (underlying releases)

        combined = ru.SelectLatestPackages(packages + underlying)
        combined = dict.fromkeys(combined)
        for pkg in packages:
          if pkg in combined:
            combined[pkg] = True
        packages = []
        underlying = []
        for pkg in combined:
          if combined[pkg]:
            packages.append(pkg)
          else:
            underlying.append(pkg)

      arch_dict = ru.GroupByArch(packages)
      underlying_dict = ru.GroupByArch(underlying)
      for arch in arch_dict:
        lg.info('Checking dependency for architecture ' + arch)
        underlying_dict.setdefault(arch, [])
        vu.CheckDependency(arch_dict[arch], underlying_dict[arch])
      bu.RunWithDB(['pkg_deps', 'src_info'], DoVerify, packages)

  # Default action: only list the binary packages in the release.

  else:
    for nva in packages:
      print nva


if __name__ == '__main__':
  try:
    main()
  except KeyError:
    lg.error('Table indexing key error, terminating')
  except KeyboardInterrupt:
    lg.info('Received keyboard interrupt, terminating...')
