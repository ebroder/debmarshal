# -*- python-indent: 2 -*-
"""debmarshal setuid support module

This module provides the necessary input sanitation and command
wrappers to allow debmarshal test suites to be run by unprivileged
users.

The main privileged operations for VM-based test suites is the
networking configuration. Depending on the virtualization technology
being used, this may also include creating the guest domain, so we'll
cover that here as well.

Although debmarshal is currently using libvirt to reduce the amount of
code needed, we won't be accepting libvirt's XML config format for
these privileged operations. This both limits the range of inputs we
have to sanitize and makes it easier to switch away from libvirt in
the future.
"""

__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import errno
import fcntl
import itertools
import os
try:
  import cPickle as pickle
except ImportError:
  import pickle
import re
import subprocess
import sys

import decorator
import libvirt
from lxml import etree
import virtinst
import yaml

from debmarshal import errors


# I really wish I could somehow incorporate a PREFIX or libexecdir or
# something, but Python doesn't really want to export any of those
# through distutils/setuptools
_SETUID_BINARY = '/usr/lib/debmarshal/debmarshal-privops'


_subcommands = {}


def runWithPrivilege(subcommand):
  """Decorator for wrapping a function to ensure that it gets run with
  privileges by using a small setuid wrapper binary.

  If a function wrapped with runWithPrivilege is called by a non-root
  user, execute the setuid wrapper with the arguments passed in.

  If a function is re-executed through the setuid wrapper, the
  function arguments and keyword arguments are passed in through the
  command line in YAML.

  For security reasons, all YAML dumps and loads occur using the
  "safe" parser, which will only (de-)serialize built-in types. This
  means that arguments to and return values from functions wrapped in
  runWithPrivilege must be limited to built-ins.

  The return value or raised exceptions of the function are also
  passed from the setuid subprocess back to the caller via standard
  out, so functions wrapped in runWithPrivilege shouldn't print
  anything.

  Args:
    subcommand: This is used as the first argument to the setuid
      binary. Since the setuid binary simply executes this module, the
      subcommand is also tracked internally for dispatching
  """
  @decorator.decorator
  def _runWithPrivilege(f, *args, **kwargs):

    # If we already have our privileges
    if os.geteuid() == 0:
      return f(*args, **kwargs)
    else:

      # Make sure that the setuid binary is actually setuid root so
      # we don't get stuck in a loop
      stats = os.stat(_SETUID_BINARY)
      if not (stats.st_mode & 04000 and stats.st_uid == 0):
        raise errors.Error('%s is not setuid root' % _SETUID_BINARY)

      p = subprocess.Popen([_SETUID_BINARY,
                            subcommand,
                            yaml.safe_dump(args),
                            yaml.safe_dump(kwargs)],
                           stdin=None,
                           stdout=subprocess.PIPE,
                           close_fds=True)
      rc = p.wait()

      # This is the only place we don't use yaml.safe_load. That's
      # intentional, because the source of this string is trusted, and
      # may be an object like an exception.
      ret = yaml.load(p.stdout)
      if rc:
        raise ret
      else:
        return ret

  # The extra layer of redirection is needed if we want to both (a)
  # use the decorator module (we do, because it gives us nice
  # function-signature-preserving properties) and (b) associate a
  # subcommand with the function it's wrapping at parse time.
  def _makeRunWithPriv(f):
    _subcommands[subcommand] = f
    return _runWithPrivilege(f)

  return _makeRunWithPriv


_hostname_re = re.compile(r"([a-z0-9][a-z0-9-]{0,62}\.)+([a-z]{2,4})$", re.I)
def _validateHostname(name):
  """Check that the input is a valid, fully-qualified domain name

  Args:
    name: The hostname to validate

  Returns:
    None

  Raises:
    debmarshal.errors.InvalidInput if the hostname is not valid
  """
  if not _hostname_re.match(name):
    raise errors.InvalidInput('Invalid hostname: %s' % name)


def _loadNetworkState(virt_con=None):
  """Load state for any networks previously created by debmarshal.

  State is written to /var/run/debmarshal-networks as a pickle. Ubuntu
  makes /var/run a tmpfs, so state vanishes after reboots - which is
  good, because the networks debmarshal has created do as well.

  Not all distributions do this, though, so we loop over the networks
  in the pickle and see which ones still exist. If a network no longer
  exists, we assume that it was deleted outside of debmarshal, and we
  erase our record of it.

  Args:
    virt_con: A non-read-only libvirt.virConnect instance. If one
      isn't passed in, we'll open one of our own. It doesn't really
      matter which libvirt driver you connect to, because all of them
      share virtual networks.

  Returns:
    A list of networks. Each network is a tuple of (network_name,
      owner_uid, gateway_ip_address)
  """
  lock = open('/var/lock/debmarshal-networks', 'w+')
  fcntl.lockf(lock, fcntl.LOCK_SH)
  try:
    networks_file = open('/var/run/debmarshal-networks')
    networks = pickle.load(networks_file)
  except EnvironmentError, e:
    if e.errno == errno.ENOENT:
      return []
    else:
      raise

  if not virt_con:
    virt_con = libvirt.open('qemu:///system')

  # The default handler for any libvirt error prints to stderr. In
  # this case, we're trying to trigger an error, so we don't want
  # the printout. This suppresses the printout temporarily
  libvirt.registerErrorHandler((lambda ctx, err: 1), None)

  for i, network in enumerate(networks):
    try:
      virt_con.networkLookupByName(network[0])
    except libvirt.libvirtError:
      del networks[i]

  # Reset the error handler to its default
  libvirt.registerErrorHandler(None, None)

  return networks


def _storeNetworkState(networks):
  lock = open('/var/lock/debmarshal-networks', 'w')
  fcntl.lockf(lock, fcntl.LOCK_EX)
  networks_file = open('/var/run/debmarshal-networks', 'w')
  pickle.dump(networks, networks_file)


def _genNetworkXML(name, gateway, netmask, hosts, dhcp):
  """Given parameters for a debmarshal network, generate the libvirt
  XML specification.

  Args:
    name: Name of the network, usually debmarshal-##
    gateway: The "gateway" for the network. Although debmarshal
      networks are isolated, you still need a gateway for things like
      the DHCP server to live at
    netmask
    hosts: The hosts that will be attached to this network. It is a
      dict from hostnames to a 2-tuple of (IP address, MAC address),
      similar to the one that's returned from createNetwork
    dhcp: A bool indicating whether or not to run DHCP on the new
      network

  Returns:
    The string representation of the libvirt XML network matching the
      parameters passed in
  """

  xml = etree.Element('network')
  etree.SubElement(xml, 'name').text = name
  xml_ip = etree.SubElement(xml, 'ip',
                            address=gateway,
                            netmask=netmask)

  if dhcp:
    # TODO(ebroder): In spite of taking the netmask as an argument,
    # this doesn't actually use the netmask to find the range of IP
    # addresses to assign over DHCP
    subnet = gateway.rsplit('.', 1)[0]

    xml_dhcp = etree.SubElement(xml_ip, 'dhcp')
    etree.SubElement(xml_dhcp, 'range',
                     start='%s.2' % subnet,
                     end='%s.254' % subnet)

    for hostname, hostinfo in hosts.iteritems():
      etree.SubElement(xml_dhcp, 'host',
                       name=hostname,
                       ip=hostinfo[0],
                       mac=hostinfo[1])

  return etree.tostring(xml)


@runWithPrivilege('create-network')
def createNetwork(hosts, dhcp=True):
  """All of the networking config you need for a debmarshal test rig.

  createNetwork creates an isolated virtual network within libvirt. It
  picks an IP address space that is as-yet unused (within debmarshal),
  and assigns that to the network. It then allocates IP addresses and
  MAC addresses for each of the hostnames listed in hosts.

  createNetwork tracks which users created which networks, and
  debmarshal will only allow the user that created a network to attach
  VMs to it or destroy it.

  Currently IP addresses are allocated in /24 blocks from
  10.100.0.0/16. 100 was chosen both because it is the ASCII code for
  "d" and to try and avoid people using the lower subnets in 10/8.

  This does mean that debmarshal currently has an effective limit of
  256 test suites running simultaneously. But that also means that
  you'd be running at least 256 VMs simultaneously, which would
  require some pretty impressive hardware.

  Args:
    hosts: A list of hostnames that will eventually be attached to
      this network
    dhcp: Whether to use DHCP or static IP addresses. If dhcp is True
      (the default), createNetwork also configures dnsmasq listening
      on the new network to assign IP addresses

  Returns:
    A 4-tuple containing:
      Network name: This is used to reference the newly created
        network in the future. It is unique across the local
        workstation
      Gateway: The network address. Also the DNS server, if that
        information isn't being grabbed over DHCP
      Netmask: The netmask for the network
      VMs: A dict mapping hostnames in hosts to (IP address, MAC
        address), as assigned by createNetwork
  """
  # First, input validation. Everything in hosts should be a valid
  # hostname
  for h in hosts:
    _validateHostname(h)

  # We don't really care which particular libvirt driver we connect
  # to, because they all share the same networking
  # config. libvirt.open() is supposed to take None to indicate a
  # default, but it doesn't seem to work, so we pass in what's
  # supposed to be the default for root.
  virt_con = libvirt.open('qemu:///system')

  networks = _loadNetworkState(virt_con)
  net_names = set(n[0] for n in networks)
  net_gateways = set(n[2] for n in networks)

  # Now we actually can allocate the new network.
  #
  # First, let's figure out what to call this network
  for i in itertools.count(0):
    net_name = 'debmarshal-%d' % i
    if net_name not in net_names:
      break

  # Then find a network to assign
  for net in itertools.count(0):
    net_gateway = '10.100.%d.1' % net
    if net_gateway not in net_gateways:
      break

  # Assign IP addresses and MAC addresses for every host that's
  # supposed to end up on this network
  net_hosts = {}
  i = 2
  for host in hosts:
    # Use the virtinst package's MAC address generator because it's
    # easier than writing another one for ourselves.
    #
    # This does mean that the MAC addresses are allocated from
    # Xensource's OUI, but whatever
    mac = virtinst.util.randomMAC()
    ip = '10.100.%d.%d' % (net, i)
    net_hosts[host] = (ip, mac)
    i += 1

  net_mask = '255.255.255.0'

  xml = _genNetworkXML(net_name, net_gateway, net_mask, net_hosts, dhcp)
  virt_net = virt_con.networkDefineXML(xml)
  virt_net.create()
  networks.append((net_name, os.getuid(), net_gateway))

  # Record the network information into our state file
  try:
    _storeNetworkState(networks)
  except:
    virt_net.destroy()
    raise

  return (net_name, net_gateway, net_mask, net_hosts)


def usage():
  """Command-line usage information for debmarshal.privops.

  Normal users are never expected to trigger this, because normal
  users are never supposed to run debmarshal.privops directly; instead
  other debmarshal scripts should use functions in this module, which
  results in the setuid re-execution.

  But just in case someone runs it directly, we'll tell them what it
  does.
  """
  print >>sys.stderr, ("Usage: %s subcommand args kwargs" %
                       os.path.basename(sys.argv[0]))
  print >>sys.stderr
  print >>sys.stderr, "  args is a YAML-encoded list"
  print >>sys.stderr, "  kwargs is a YAML-encoded dict"


def main(args):
  """Dispatch module invocations.

  A sort of other half of the runWithPrivilege decorator, main parses
  the arguments and kwargs passed in on the command line and calls the
  appropriate function. It also intercepts any raised exceptions or
  return values, serializes them, and passes them over standard out to
  whatever invoked the module.

  Note: this doesn't intercept exceptions raised as part of the
  initial argument parsing, because we're optimistically assuming that
  arguments that come in from runWithPrivilege are flawless
  (heh...). Those exceptions will get rendered by the Python
  interpreter to standard error, as will any errors that we generate.

  Args:
    args, a list of arguments passed in to the module, not including
      argv[0]

  Returns:
    Return an integer, which becomes the exit code for when the module
      is run as a script.
  """
  if len(args) != 3:
    usage()
    return 1

  subcommand, posargs, kwargs = args
  posargs = yaml.safe_load(posargs)
  kwargs = yaml.safe_load(kwargs)

  priv_func = _subcommands[subcommand]

  try:
    ret = priv_func(*posargs, **kwargs)
    rc = 0
  except Exception, e:
    ret = e
    rc = 1

  # This is the only place we don't use yaml.safe_dump, because this
  # output is trusted when it gets parsed, and we want to be able to
  # pass around arbitrary objects
  print yaml.dump(ret)
  return rc


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
