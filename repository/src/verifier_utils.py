#!/usr/bin/python2.4
#
# Copyright 2006 Google Inc. All Rights Reserved.

"""Release dependency and conflict verification functions

The bsddb_utils module contains utility functions for verifying the
internal integrity of a release.  The verification checks that the
dependency graph for every package has a valid solution, and that two
packages that do not Replaces or Conflicts with each other should not
provide the same installed file.
"""

__author__ = 'cklin@google.com (Chuan-Kai Lin)'

import logging as lg
import signal
import sys
import bsddb_utils as bu
import deb_utils as du
import logging_utils as lu
import release_utils as ru


_package = None
_silent = True
_depi = None
_essential = None
_notified = None
_relation_pkg = None


# The following four functions implement common logging and error
# reporting functionality in this module.  These functions allow us to
# turn off warning and error messages (useful when solving negatively
# formulated problems, for which failure is success), they suppress
# repeated messages to make the logs cleaner, and they log the package
# being processed only when there are warnings or errors.

def _Warning(text):
  global _package, _silent
  if not _silent:
    if _package:
      lg.info('Validating ' + _package + ' ...')
      _package = None
    lg.warning(text)


def _Error(text):
  global _package, _silent
  if not _silent:
    if _package:
      lg.info('Validating ' + _package + ' ...')
      _package = None
    lg.error(text)


def _ReportConflict(pkg1, pkg2):
  if pkg1 not in _notified:
    _Warning(pkg1 + ' conflicts with ' + pkg2)
    _notified[pkg1] = None
    _notified[pkg2] = None


def _ReportUnsatisfiableRelation(relation):
  if relation not in _notified:
    _Warning('Cannot fulfill dependency ' + relation)
    _notified[relation] = None


def _BuildDependencyGraph(pkg_list, pkg_deps):
  """Organize dependency information for a release

  This function organizes dependency metadata for packages listed in
  the pkg_list argument in a form readily usable for dependency and
  implicit conflict checking.  The entry for each package is a tuple
  with the following attributes: name_ver_arch, Depends (including
  Pre-Depends), Conflicts, and Replaces.  The key to _depi is a
  virtual or actual package name, which maps to a list of
  corresponding package entries.
  """

  global _depi, _essential

  pkgs_to_check = {}
  for nva in sorted(pkg_list):
    [n, v, a] = nva.split('_')
    di = pkg_deps[nva]

    # Ignore debian-installer packages.  Since they are not
    # installable on a normal system, they can have all kinds of
    # dependency breakage and we do not really care.

    if di['Component'][0].endswith('/debian-installer'):
      continue

    if di['Essential'][0] != 'no':
      _essential.append([nva])

    pkgs_to_check[nva] = None
    dep = di['Depends']
    dep.extend(di['Pre-Depends'])
    cfl = di['Conflicts']
    repl = di['Replaces']

    # Allow looking up the _depi entry for a package through both
    # actual and virtual (defined with Provides) package names.

    for name in [n] + di['Provides']:
      if name not in _depi:
        _depi[name] = []
      _depi[name].append((nva, dep, cfl, repl))
  return pkgs_to_check


def _BuildConflictList(file_pkg, pkg_dict):
  """Build a list of implicitly conflicting packages

  Two packages conflict implicitly if they both install a file to the
  same path but neither declares Conflicts or Replaces on the other.
  This function compiles a list of implicitly conflicting package
  pairs in the release.
  """

  cfl = {}
  for f in file_pkg:
    mutual_ex = {}

    # Add packages in the release that contain the pathname f into the
    # mutual_ex dictionary.

    for pkg in file_pkg[f].split(', '):
      entry = _GetPackage(pkg)
      if entry is not None:
        mutual_ex[pkg] = entry

    # Add all implicitly conflicting package pairs in mutual_ex into
    # the cfl dictionary, with the conflicted pathname f as the value.

    for p1 in mutual_ex:
      for p2 in mutual_ex:
        if p1 >= p2:  continue
        if not (p1 in pkg_dict or p2 in pkg_dict):  continue
        if _MatchRelations(mutual_ex[p1][3], p2, True):  continue
        if _MatchRelations(mutual_ex[p2][3], p1, True):  continue
        if _MatchRelations(mutual_ex[p1][2], p2):  continue
        if _MatchRelations(mutual_ex[p2][2], p1):  continue
        cfl[(p1, p2)] = f
  return cfl


def _MatchRelations(relations, nva, strict=False):
  """See if the package matches any of the relations
  """

  for relation in relations:
    if nva in _SelectPackagesByRelation(relation, strict):
      return True
  return False


def _SelectPackagesWithMemo(relation):
  """Memoized version of _SelectPackagesByRelation()
  """

  global _relation_pkg

  if relation not in _relation_pkg:
    _relation_pkg[relation] = _SelectPackagesByRelation(relation)
  return _relation_pkg[relation]


def _SelectPackagesByRelation(relation, strict=False):
  """Find packages that satisfy the given relation

  This function finds all packages that satisfy the given single
  relation (possibly with | alternatives).  If the strict flag is set,
  the function matches only actual package names and not virtual ones;
  we need this feature to work with Replaces.
  """

  if relation.find(' | ') != -1:
    results = {}
    for part in relation.split(' | '):
      results.update(_SelectPackagesByRelation(part, strict))
    return results

  try:
    results = {}
    name = relation.split(' ')[0]
    for entry in _depi[name]:
      nva = entry[0]

      # Match both actual and virtual package names (not versioned)

      if relation.find(' ') == -1 and not strict:
        results[nva] = None

      # Match only actual package names (versioned dependency or
      # strict matching)

      elif ru.CheckPackageRelation(nva, relation):
        results[nva] = None
    return results
  except KeyError:
    return {}


def _GetPackage(nva):
  """Retrieve a _depi package entry by name_version_arch
  """

  name = nva.split('_')[0]
  try:
    for entry in _depi[name]:
      if entry[0] == nva:
        return entry
  except KeyError:
    pass
  _Warning('Package ' + nva + ' is not in the release')
  return None


def _DoComputeDependency(queue, base, exclude):
  """Find a dependency solution for a set of packages

  This function determines a minimum set of packages that satisfies
  the transitive dependency relation of the given set of packages.
  The queue argument is the list of alternative packages that we wish
  to install (eg., [['foo_3_all'], ['bar_1_all', 'buz_1_all']] means
  that we wish to install either foo and bar, or foo and buz), and the
  base dictionary has the set of currently installed packages as its
  keys.  The exclude dictionary has the set of packages that must not
  be installed (eg., due to Conflicts).  The function returns None if
  it cannot find any such solution.
  """

  global _notified

  # If there are no packages in the queue, we are done tracing the
  # dependency graph and the base is the answer.

  if queue == []:
    return base.keys()

  # The head are the packages we want to try fit into base, and the
  # packages in queue we will deal with later.

  head = queue[0]
  tail = queue[1:]

  # If there is a package in head that is already in base, then a
  # package we want has already been included, and we can continue
  # working on the tail of the queue.

  for pkg in head:
    if pkg in base:
      return _DoComputeDependency(tail, base, exclude)

  # Try to add each package in head into base in turn and call
  # _DoComputeDependency() recursively in a depth-first search.

  for pkg in head:

    # Skip with a warning message if some package in base conflicts
    # with this one.

    if pkg in exclude:
      _ReportConflict(exclude[pkg], pkg)
      continue

    entry = _GetPackage(pkg)

    # Skip if the package is not in the release (this situation should
    # never happen).

    if entry is None:
      _Warning('Bug: package ' + pkg + ' does not exist')
      continue

    # Skip if this package conflicts with any package in base;
    # otherwise add the Conflicts packages to new_exclude.  Note that
    # following Policy 7.3, we do not check if the package Conflicts
    # with itself.

    proceed = True
    new_exclude = dict(exclude)
    for relation in entry[2]:
      for conflicted in _SelectPackagesWithMemo(relation):
        if conflicted in base:
          _ReportConflict(pkg, conflicted)
          proceed = False
          break
        new_exclude[conflicted] = pkg
      if not proceed:
        break
    if not proceed:
      continue

    # Add dependencies of this package into new_queue.

    new_queue = list(tail)
    for relation in entry[1]:
      depends = sorted(_SelectPackagesWithMemo(relation).keys())

      # There are no packages in the release which satisfies the
      # dependency, we know that there cannot be any solutions in this
      # branch of the search tree and skip with a warning message.

      if depends == []:
        _ReportUnsatisfiableRelation(relation)
        return None

      # To speed up the search process, we insert dependencies with
      # only one choice to the beginning of the queue, and all others
      # at the tail.

      if len(depends) == 1:
        new_queue.insert(0, depends)
      else:
        new_queue.append(depends)

    # Add this package to the new_base dictionary.

    new_base = dict(base)
    new_base[pkg] = None

    # Continue working on the queue.

    result = _DoComputeDependency(new_queue, new_base, new_exclude)
    if result is not None:
      return result

  return None


def _ComputeDependency(queue):
  """Wrapper function for _DoComputeDependency()

  This function adds a 5-second timeout to the dependency solving
  procedure to avoid blocking on particularly difficult cases.  On a
  2.6GHz Xeon system, the dependency for nearly all packages are
  solved in fractions of a second.  This function also inserts the set
  of Essential packages into the queue to catch any package that
  conflicts with them.
  """

  global _notified

  def Handler(signum, frame):
    _Error('Cannot solve dependency within time bound')
    raise MemoryError

  try:
    try:
      _notified = {}
      signal.signal(signal.SIGALRM, Handler)
      signal.alarm(5)
      return _DoComputeDependency(_essential + queue, {}, {})
    except MemoryError:
      return None
  finally:
    signal.alarm(0)


def CheckDependency(pkg_list, underlying=[]):
  """Verify dependency integrity of a release
  """

  global _package, _silent, _relation_pkg

  def Initialize(_arg, dbs):
    global _depi, _essential

    _depi = {}
    _essential = []
    pkg_deps = du.ParseDependencyTable(dbs['pkg_deps'])
    _BuildDependencyGraph(underlying, pkg_deps)
    pkgs_to_check = _BuildDependencyGraph(pkg_list, pkg_deps)
    cfl = _BuildConflictList(dbs['file_pkg'], pkgs_to_check)
    return cfl, pkgs_to_check

  sys.setrecursionlimit(10000)
  db_list = ['pkg_deps', 'file_pkg']
  cfl, pkgs_to_check = bu.RunWithDB(db_list, Initialize)

  _silent = False
  _relation_pkg = {}

  # Check that every individual package is installable.

  for pkg in sorted(pkgs_to_check.keys()):
    _package = pkg
    if _GetPackage(pkg) is None:
      _Error('Package ' + pkg + ' does not exist')
    elif _ComputeDependency([[pkg]]) is None:
      _Error(pkg + ' is uninstallable')

  # Check that packages providing the same pathnames contain metadata
  # that prevents them from being installed at the same time.

  _silent = True
  for pkg_1, pkg_2 in sorted(cfl.keys()):
    if _ComputeDependency([[pkg_1], [pkg_2]]) is not None:
      lg.error('Implicit conflict between ' + pkg_1 + ' and '
               + pkg_2 + ' on /' + cfl[(pkg_1, pkg_2)])


def main():
  def CompileList(_arg, dbs):
    latest = ru.SelectLatestPackages(dbs['pkg_info'])
    return ru.GroupByArch(latest)

  lu.SetLogConsole()
  arch_dict = bu.RunWithDB(['pkg_info'], CompileList, None)
  for arch in arch_dict:
    lg.info('Checking dependency for architecture ' + arch)
    CheckDependency(arch_dict[arch])


if __name__ == '__main__':
  try:
    main()
  except KeyboardInterrupt:
    lg.info('Received keyboard interrupt, terminating...')
