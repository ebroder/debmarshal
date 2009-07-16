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

"""Release management and publishing utility functions

The bsddb_utils module contains utility functions for defining and
publishing releases.  The functionality includes grouping binary
packages by various attributes, comparing package versions, checking
package relations (based on Policy 7.1), and filtering package lists.
"""

__author__ = 'cklin@google.com (Chuan-Kai Lin)'

import logging as lg
import os
import re
import shutil
import sys
import time
import alias_utils as au
import bsddb_utils as bu
import crypto_utils as cu
import deb_utils as du
import os_utils as ou
import setting_utils as su


def GroupByComponent(nva_list, dep_dict):
  """Categorize a list packages by their component
  """

  comp_dict = {}
  for nva in nva_list:
    comp = dep_dict[nva]['Component'][0]
    if comp not in comp_dict:
      comp_dict[comp] = []
    comp_dict[comp].append(nva)
  return comp_dict


def GroupByArch(nva_list):
  """Categorize a list packages by their architecture

  Based on the input binary package list, this function returns a
  dictionary that maps an architecture name to its packages.
  Binary-dependent packages are handled in the obvious manner, and
  binary-independent ones go into all architectures listed in the
  Architectures attribute in the repository configuration file.
  """

  arch_dict = {}
  for nva in nva_list:
    arch = nva.split('_')[2]
    if arch not in arch_dict:
      arch_dict[arch] = []
    arch_dict[arch].append(nva)

  archs = su.GetSetting(None, 'Architectures').split(', ')
  if 'all' in arch_dict:
    all = arch_dict['all']
    del arch_dict['all']
    for arch in archs:
      arch_dict.setdefault(arch, [])
      arch_dict[arch].extend(all)
      arch_dict[arch].sort()
  return arch_dict


def CollectSources(nva_list, pkg_deps, src_info):
  """Find sources for the given binary packages

  This function tries to find a list of source packages that can be
  used to build all binary packages in the first argument.  Note that
  since Ubuntu dapper contains many binary packages without source, we
  tolerate missing source packages and gives only a warning.
  """

  src_dict = {}
  for nva in nva_list:
    nv = pkg_deps[nva]['Source'][0]
    if nv in src_info:
      src_dict[nv] = None
    else:
      lg.warning(nva + ' does not have a source package')
  return sorted(src_dict.keys())


# The following five version-comparison functions are implemented in
# accordance with Debian Policy 3.7.2, Section 5.6.12, except for
# tilda (sorted less than everything), which is not yet official.

def _SplitSubVersion(string):
  """Extract initial digit and non-digit parts in a version string
  """

  head1 = ''
  for ch in string:
    if ch.isdigit():  break
    head1 = head1 + ch
  string = string[len(head1):]

  head2 = ''
  for ch in string:
    if not ch.isdigit():  break
    head2 = head2 + ch
  string = string[len(head2):]
  if head2 == '':  head2 = '0'

  return head1, head2, string


def _SplitVersion(string):
  """Split a version into epoch, upstream, and debian parts
  """

  colon = string.find(':')
  uscore = string.rfind('-')

  epoch = ''
  if colon != -1:
    epoch = string[:colon]

  debv = ''
  if uscore != -1:
    debv = string[uscore+1:]
  else:
    uscore = len(string)
  return epoch, string[colon+1:uscore], debv


def _CompareString(str1, str2):
  """Compare two strings in Debian lexical order
  """

  bound = max(len(str1), len(str2))
  str1 = str1.ljust(bound)
  str2 = str2.ljust(bound)
  index = 0
  while index<bound:
    c1 = str1[index]
    c2 = str2[index]
    if c1 == '~' and c2 != '~':  return -1
    if c2 == '~' and c1 != '~':  return 1
    if c1 == ' ' and c2 != ' ':  return -1
    if c2 == ' ' and c1 != ' ':  return 1
    a1 = c1.isalpha()
    a2 = c2.isalpha()
    if a1 and not a2:  return -1
    if a2 and not a1:  return 1
    c = cmp(c1, c2)
    if c:  return c
    index = index+1
  return 0


def _CompareSubVersion(ver1, ver2):
  """Compare a specific part of two version strings
  """

  while ver1 != '' or ver2 != '':
    s1, n1, ver1 = _SplitSubVersion(ver1)
    s2, n2, ver2 = _SplitSubVersion(ver2)
    c = _CompareString(s1, s2)
    if c != 0:  return c
    c = cmp(int(n1), int(n2))
    if c != 0:  return c
  return 0


def CompareVersion(ver1, ver2):
  """Compare two full version strings (Policy 5.6.12)
  """

  e1, u1, d1 = _SplitVersion(ver1)
  e2, u2, d2 = _SplitVersion(ver2)

  c = _CompareSubVersion(e1, e2)
  if c != 0:  return c
  c = _CompareSubVersion(u1, u2)
  if c != 0:  return c
  return _CompareSubVersion(d1, d2)


def SelectLatestPackages(nva_list):
  """Select the latest packages from the given list
  """

  ver_dict = {}
  for nva in nva_list:
    desc = nva.split('_')
    na = desc[0], desc[2]
    ver = desc[1]
    if na in ver_dict:
      current_ver = ver_dict[na]
      if CompareVersion(ver, current_ver) <= 0:
        continue
    ver_dict[na] = ver

  latest = []
  for name, arch in ver_dict:
    ver = ver_dict[(name, arch)]
    latest.append('_'.join([name, ver, arch]))
  return sorted(latest)


# These are the attribute keys in Release files.

_RELEASE_KEYS = ['Archive', 'Version', 'Component', 'Origin',
                 'Label', 'Architecture', 'Description']


def _WriteInfoFile(info_dict, keys, rel_dict, name):
  """Write a Sources/Packages file with Release

  This function writes the Release file for a leaf dists/ directory
  and the corresponding package information file (Packages for
  binary-arch and Sources for source).  The keys argument is the list
  of packages for the information file (nva for binary-arch and nv for
  source), and name is the name for the information file.
  """

  path, filename = os.path.split(name)
  if not os.path.exists(path):
    os.makedirs(path, 0755)

  # Write the Release file.

  f = open(os.path.join(path, 'Release'), 'w')
  for key in _RELEASE_KEYS:
    if rel_dict[key] is None:  continue
    f.write(key + ': ')
    f.write(rel_dict[key])
    f.write('\n')
  f.close()

  # Write the Packages/Sources file.

  f = open(name, 'w')
  for key in keys:
    f.write(info_dict[key])
    f.write('\n\n')
  f.close()

  # Make a gzipped copy.  The -n flag asks gzip not to include the
  # file timestamp in the compressed result so that files generated
  # from different runs will have the same cryptographic hash values.

  shutil.copy(name, name + '.copy')
  ou.SpawnProgram(['/bin/gzip', '-9', '-n', '-f', name])
  os.rename(name + '.copy', name)


# These are the attribute keys in top-level Release files.

_TOP_RELEASE_KEYS = ['Origin', 'Label', 'Suite', 'Version',
                     'Codename', 'Date', 'Architectures',
                     'Components', 'Description']


def _WriteTopReleaseFile(rel_dict):
  """Write release-top-level Release file
  """

  def DoFingerPrint(files, path, names):
    for name in sorted(names):
      pathname = os.path.join(path, name)
      if not os.path.isfile(pathname):
        continue
      files.append(('/'.join(pathname.split('/')[3:]),
                    str(os.path.getsize(pathname)),
                    cu.GetMD5Hash(pathname),
                    cu.GetSHA1Hash(pathname)))

  dist_files = []
  archive = rel_dict['Archive']
  version = rel_dict['Version']
  path = os.path.join('dists', archive, version)
  os.path.walk(path, DoFingerPrint, dist_files)

  name = os.path.join(path, 'Release')
  f = open(name, 'w')
  for key in _TOP_RELEASE_KEYS:
    if rel_dict[key] is None:  continue
    f.write(key + ': ')
    f.write(rel_dict[key])
    f.write('\n')
  f.write('MD5Sum:\n')
  for p, s, md5, sha1 in dist_files:
    f.write(' '.join(['', md5, s.rjust(16), p]) + '\n')
  f.write('SHA1:\n')
  for p, s, md5, sha1 in dist_files:
    f.write(' '.join(['', sha1, s.rjust(16), p]) + '\n')
  f.close()
  cu.MakeReleaseSignature(name)


def _LoadReleaseInfo(track, version):
  """Set up release metadata based on configuration settings

  This function set up appropriate release metadata based on the
  maintenance track configuration attributes and on how apt likes
  things to be done.  Most of the attributes do not appear to be of
  importance, and the only gotcha I have found so far is that apt
  complains unless Suite is the same as Archive.
  """

  rel_dict = {}
  rel_dict['Archive'] = track
  rel_dict['Suite'] = track
  rel_dict['Codename'] = su.GetSetting(track, 'Codename')
  rel_dict['Date'] = time.strftime('%a, %d %b %Y %H:%M:%S %Z')
  rel_dict['Version'] = version
  rel_dict['Origin'] = su.GetSetting(track, 'Origin')
  rel_dict['Label'] = su.GetSetting(track, 'Label')
  rel_dict['Description'] = su.GetSetting(track, 'Description')
  return rel_dict


def _GenerateReleaseWithDB(track, version, packages, dbs):
  """Generate and publish a release with Berkeley DB input

  This function generates and publishes a release; the -WithDB suffix
  suggests that you should run it under bu.RunWithDB().  It either
  republishes an existing release (packages is None) or generate and
  publish a new release from a list of binary packages to be included
  (version is None).
  """

  pkg_info = dbs['pkg_info']
  src_info = dbs['src_info']
  pkg_deps = du.ParseDependencyTable(dbs['pkg_deps'])
  releases = dbs['releases']
  aliases = dbs['aliases']

  new_release = True

  # Set up binary package list and release number depending on which
  # mode of operation we are in.

  if packages is None and version is not None:
    release = track + '/' + version
    result = FetchReleaseList(release, releases, aliases)
    if result is None:
      lg.error('There is no such a release called ', release)
      raise ValueError
    packages, release = result
    new_release = False
    version = release.split('/')[1]
    shutil.rmtree(os.path.join('dists', release), ignore_errors=True)
  elif version is None and packages is not None:
    version = str(_GetNextReleaseNumber(track, releases))
  else:
    lg.error('Only one of packages and version should be specified')
    raise ValueError

  # Make sure that all referenced binary packages correspond to
  # package files that have been indexed in the pool.

  if not ValidateReleaseList(packages, pkg_info):
    lg.error('Release package list validation failed')
    raise ValueError

  # Make sure that the release contains at least one package.

  if packages == []:
    lg.error('Cannot build release with no packages')
    return

  comp_dict = GroupByComponent(packages, pkg_deps)
  rel_dict = _LoadReleaseInfo(track, version)

  for comp in comp_dict:
    rel_dict['Component'] = comp
    comp_dir = os.path.join('dists', track, version, comp)
    arch_dict = GroupByArch(comp_dict[comp])

    # Write Release and Packages files for each architecture.

    for arch in arch_dict:
      rel_dict['Architecture'] = arch
      output = os.path.join(comp_dir, 'binary-'+arch, 'Packages')
      _WriteInfoFile(pkg_info, arch_dict[arch], rel_dict, output)

    # Write Release and Sources files for the source directory.

    rel_dict['Architecture'] = 'source'
    output = os.path.join(comp_dir, 'source', 'Sources')
    nvs = CollectSources(comp_dict[comp], pkg_deps, src_info)
    _WriteInfoFile(src_info, nvs, rel_dict, output)

  # Write the top-level Release file.

  arch_list = sorted(GroupByArch(packages).keys())
  rel_dict['Architectures'] = ' '.join(arch_list)
  comp_list = []
  for comp in comp_dict:
    if not comp.endswith('/debian-installer'):
      comp_list.append(comp)
  rel_dict['Components'] = ' '.join(sorted(comp_list))
  _WriteTopReleaseFile(rel_dict)

  # Update database tables to record the new release

  if new_release:
    releases[track+'/'+version] = ', '.join(packages)
    au.UpdateAlias(aliases, releases, track+'/latest', version)
    au.RefreshAlias(aliases)


def GenerateReleaseVersion(track, version):
  """Republish a specific release in a maintenance track
  """

  def DoGenerate(_arg, dbs):
    _GenerateReleaseWithDB(track, version, None, dbs)
  bu.RunWithDB(None, DoGenerate)


def GenerateReleaseList(track, packages):
  """Generate a new release from a list of binary packages
  """

  def DoGenerate(_arg, dbs):
    _GenerateReleaseWithDB(track, None, packages, dbs)
  bu.RunWithDB(None, DoGenerate)


def FetchReleaseList(release, release_db, alias_db):
  """Fetch the list of packages in an existing release
  """

  track = release.split('/')[0]
  r = au.LookupAlias(alias_db, release_db, release)
  release = track + '/' + r
  return release_db[release].split(', '), release


def _GetNextReleaseNumber(track, release_db):
  """Get the next available release version number
  """

  version = -1
  for key in release_db:
    [t, v] = key.split('/', 1)
    if t == track and int(v) > version:
      version = int(v)
  return version+1


def GetUpstreamReleaseList(dist_dir):
  """Return the list of packages mentioned in Packages files

  This function walks through the given path, finds all Packages files
  in subdirectories, and compiles a list of all binary packages
  mentioned in those Packages files.
  """

  def DoTraverse(_arg, dir, _names):
    name = os.path.join(dir, 'Packages')
    ou.RunWithFileInput(DoParse, name)

  def DoParse(lines):
    try:
      name = ''
      arch = ''
      for line in lines:
        line = line.rstrip('\n')
        if line.startswith('Package: '):
          name = line.split(' ', 1)[1]
        if line.startswith('Architecture: '):
          arch = line.split(' ', 1)[1]
        if line.startswith('Version: '):
          version = line.split(' ', 1)[1]
          pkg_dict['_'.join([name, version, arch])] = None
    except IOError:
      pass

  pkg_dict = {}
  if not os.path.isdir(dist_dir):
    lg.error(dist_dir + ' is not a directory')
  os.path.walk(dist_dir, DoTraverse, None)
  return sorted(pkg_dict.keys())


def ValidateReleaseList(pkg_list, pkg_info):
  """Check for unknown packages in the list

  This function checks whether every package in the argument list has
  previously been indexed (as a key to the pkg_info table).  We do not
  exit the loop as soon as we find one unknown package so that we can
  log all such errors.
  """

  good = True
  for nva in pkg_list:
    if nva not in pkg_info:
      lg.warning('Package ' + nva + ' is not in the pool')
      good = False
  return good


def CheckPackageRelation(package, relation, ver_match=True):
  """Test if a package satisfies a relation

  This function tests if a package satisfies a relation based on
  Policy 7.1.  I added two extensions to make package relations more
  useful in release specification files: a single bang (!) excludes
  all versions of the package, and the != operator excludes only a
  specific version.  The function returns None if the test does not
  result in either a definite positive or a definite negative match.
  """

  # A lone package name matches every package with that name.

  name_re = re.compile(r'\A[^_ ]+\Z')
  if name_re.match(relation):
    if not package.startswith(relation + '_'):
      return None
    return True

  # A name with a bang (!) matches against packages with that name.

  neg_re = re.compile(r'\A[^_ ]+ !\Z')
  if neg_re.match(relation):
    name = relation.split(' ')[0]
    if not package.startswith(name + '_'):
      return None
    return False

  # A name with '(op ver)' suffix matches against specific versions.
  # We return False if the versioned match fails, or the ver_match
  # value if the match succeeds.  We need to parameterize the
  # successful match return value because we want it to return None
  # for release specification file processing, and True for dependency
  # checking (in verifier_utils).

  cond_re = re.compile(r'\A[^_ ]+ \([<>=!]+ [^_ ]+ *\)\Z')
  if cond_re.match(relation):
    [name, op, ver] = relation.split(' ', 2)
    [pkg_name, pkg_ver, pkg_arch] = package.split('_')
    if pkg_name != name:
      return None
    op = op[1:]
    ver = ver[:-1].strip()
    cmp_result = CompareVersion(pkg_ver, ver)
    if op == '<<':
      if not cmp_result <  0:  return False
    elif op == '>>':
      if not cmp_result >  0:  return False
    elif op == '<=':
      if not cmp_result <= 0:  return False
    elif op == '>=':
      if not cmp_result >= 0:  return False
    elif op == '!=':
      if not cmp_result != 0:  return False
    elif op == '<':
      if not cmp_result <= 0:  return False
    elif op == '>':
      if not cmp_result >= 0:  return False
    elif op == '=':
      if not cmp_result == 0:  return False
    else:
      lg.warning('Ill-formed relation ' + relation)
      return None
    return ver_match

  lg.warning('Ill-formed relation ' + relation)
  return None


# The following five functions are used to determine which versions of
# a package should be considered candidates for a release.  The
# primary data structure used by these functions is a version
# dictionary, which maps a (name, arch) pair to a list of version
# numbers considered for this package.

def CollectPackageVersions(pkg_iter):
  """Build initial version dictionary from package iterator

  This package uses a package iterator (typically the pkg_info
  Berkeley DB table) to collect the available versions of each package
  and to build an initial version dictionary.  The list of available
  versions are sorted in descending order (latest first).
  """

  ver_dict = {}
  for nva in pkg_iter:
    [n, v, a] = nva.split('_')
    if (n, a) not in ver_dict:
      ver_dict[(n, a)] = []
    ver_dict[(n, a)].append(v)
  for key in ver_dict:
    ver_dict[key].sort(CompareVersion)
    ver_dict[key].reverse()
  return ver_dict


def FilterVersionWithFile(ver_dict, name):
  """Filter a version dictionary with a release spec file

  This function reads a release specification file and uses its
  contents to drop package versions that the release engineer wishes
  to exclude.  A line that starts with a hash (#) is a comment.
  """

  def DoFilter(lines):
    try:
      stripped = []
      for line in lines:
        line = line.split('#')[0]
        if line == '' or line.isspace():  continue
        stripped.append(line.rstrip('\n'))
      return _FilterVersionWithList(ver_dict, stripped)
    except IOError:
      lg.debug('Release spec file ' + name + ' does not exist')
      return ver_dict

  return ou.RunWithFileInput(DoFilter, name)


def _FilterVersionWithList(ver_dict, relations):
  """Filter each package version with the relation list

  Test each available version in the version dictionary against the
  list of relations (from a release specification file).  Returns a
  new dictionary with the filtered versions.
  """

  new_dict = {}
  for n, a in ver_dict:
    filtered = []
    for v in ver_dict[(n, a)]:
      nva = '_'.join([n, v, a])
      if _MatchInclusionList(nva, relations):
        filtered.append(v)
    new_dict[(n, a)] = filtered
  return new_dict


def _MatchInclusionList(package, relations):
  """Filter a package nva with the relation list

  This function is the inner loop in _FilterVersionWithList() that
  also interprets the catch-all '+' relation.
  """

  for relation in relations:
    if relation == '+':
      return True
    res = CheckPackageRelation(package, relation, None)
    if res is not None:
      return res
  return False


def CutOffVersions(ver_dict, nvas):
  """Drop any package version higher than given in the list

  This function enforces the practice that a release should never
  contain a package whose name is not in the package list given by the
  release-engineer, or a package that has a higher version number than
  the one given in the list.  In other words, debmarshal only
  downgrades packages and not upgrade them.
  """

  cut = {}
  for nva in nvas:
    [n, v, a] = nva.split('_')
    key = n, a
    if key not in ver_dict:
      lg.error('There are no packages like ' + nva)
      continue
    while ver_dict[key] != []:
      if CompareVersion(ver_dict[key][0], v) <= 0:
        break
      ver_dict[key].pop(0)
    if ver_dict[key] == []:
      lg.error('There are no versions below ' + nva)
    else:
      cut[key] = ver_dict[key]
  return cut
