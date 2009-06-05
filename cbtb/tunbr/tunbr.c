/* tunbr
 *
 * A small setuid wrapper to allocate and permit tap devices in bridges
 * for use by virtualization tools.
 *
 * 1) run tunctl as root with -u uid to allocate and change ownership
 *    of a device
 * 2) parse tunctl output to get device name
 * 3) set IFACE environment variable to device name
 * 4) add tap device to pre-configured bridge
 * 5) fork and run as original user the rest of the commandline.
 * 6) tunctl -d IFACE as root
 *
 * compiled program must be setuid root, and executable by the group
 * permitted to use tap devices.
 *
 * Copyright 2007 Google Inc.
 * Author: Drake Diedrich
 * License: GPLv2
 ***************************************************************************/  
 
#include <sys/types.h>
#include <unistd.h>
#include <stdio.h>
#include <errno.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <strings.h>
#include <stdlib.h>
#include <time.h>
#include <signal.h>
#include <string.h>
#include <sys/wait.h>

extern char **environ;

    
#ifndef BRIDGE
#define BRIDGE "br1"
#endif

#ifndef TUNCTL
#define TUNCTL "/usr/sbin/tunctl"
#endif

#ifndef BRCTL
#define BRCTL "/usr/sbin/brctl"
#endif

#ifndef IFCONFIG
#define IFCONFIG "/sbin/ifconfig"
#endif

#ifndef PXELINUXCFGDIR
#define PXELINUXCFGDIR "/tftpboot/pxelinux.cfg/"
#endif

#ifndef LEASES
#define LEASES "/var/lib/misc/tunbr.dnsmasq"
#endif

#ifndef NEWLEASES
#define NEWLEASES "/var/lib/misc/tunbr.dnsmasq.new"
#endif

#ifndef IP0
#define IP0 192
#endif

#ifndef IP1
#define IP1 168
#endif

#ifndef IP2
#define IP2 23
#endif

#ifndef IP3LOW
#define IP3LOW 151 
#endif

#ifndef IP3HIGH
#define IP3HIGH 253
#endif

#ifndef MAX_INSTANCES
#define MAX_INSTANCES (IP3HIGH-IP3LOW+1)
#endif


void stop_dnsmasq() {
  system("/etc/init.d/dnsmasq stop");
}

void start_dnsmasq() {
  system("/etc/init.d/dnsmasq start");
}


/* delete an entry from dnsmasq.leases (argument 1)
 * comment matching pid is deleted,
 * active line matching mac[] and ip[] is deleted.
 * all other lines are passed through verbatim. */
void del_from_leases(const char *leases, const char *newleases,
		      const unsigned char mac[6], const unsigned char ip[4]) {
  int ofd;
  FILE *ifp;
  int iip[4], imac[6];
  int pid, mpid;
  int n, s, rv;
  char *buffer=NULL;
  int bufsize=0;
  time_t t;

  stop_dnsmasq();

  ofd = open(newleases, O_WRONLY|O_CREAT|O_EXCL, 0644);
  if (ofd == -1) {
    fprintf(stderr, "Unable to open %s exclusively.  "
	    "Either a rare collision occured and rerunning the previous "
	    "command will succeed, "
	    "or the file was abandoned in the middle of an atomic operation "
	    "and should be deleted.\n",
	    newleases);
    return;
  }


  mpid = getpid();

  ifp = fopen(leases, "r");
  if (ifp) {
    while ((s = getline(&buffer, &bufsize, ifp)) > 0) {
      n=sscanf(buffer, "dhcp-host=%x:%x:%x:%x:%x:%x,%d.%d.%d.%d",
	       imac+0, imac+1, imac+2, imac+3, imac+4, imac+5,
	       iip+0, iip+1, iip+2, iip+3);
      if (n==10) {
	if (iip[0]==ip[0] && iip[1]==ip[1] && iip[2]==ip[2] && iip[3]==ip[3] &&
	    imac[0]==mac[0] && imac[1]==mac[1] && imac[2]==mac[2] &&
	    imac[3]==mac[3] && imac[4]==mac[4] && imac[5]==mac[5]) {
	    time_t t=time(NULL);
	    fprintf(stderr,
	       "%s: tunbr deleting %x:%x:%x:%x:%x:%x %d.%d.%d.%d\n",
	       ctime(&t),
	       imac[0], imac[1], imac[2], imac[3], imac[4], imac[5],
	       iip[0], iip[1], iip[2], iip[3]);
	  continue;
	}
      }

      n=write(ofd, buffer, s);
      if (n != s) {
	fprintf(stderr, "short write to %s\n", newleases);
	perror(newleases);
      }

    }
    rv = fclose(ifp);
    if (rv == -1) {
      perror(leases);
    }
    free(buffer);
  }


  rv = close(ofd);
  if (rv == -1) {
    perror(newleases);
  }

  rv = rename(newleases, leases);
  if (rv == -1) {
    perror(newleases);
  }

  start_dnsmasq();
}


/* add a new entry to tunbr.dnsmasq (argument 1) in the IPx range
 * that does not conflict with existing entries.
 * Returns ip[4] and mac[6] with the free choices found */
void add_to_leases(const char *leases, const char *newleases,
		   unsigned char mac[6], unsigned char ip[4]) {
  FILE *ifp;
  unsigned int iip[4], imac[6];
  char *buffer=NULL;
  int bufsize=0;
  char used[256];
  int i, s, n;
  int rfd, ofd;
  int rv;
  char outbuf[512];
  time_t t;

  bzero(used, sizeof(used));

  rfd = open("/dev/urandom", O_RDONLY);
  if (rfd) {
    n = read(rfd, mac, 6);
    if (n != 6) {
      perror("short read from /dev/urandom");
      exit(2);
    }
    close(rfd);
    /* non-multicast, locally admimistered flags set
     * http://en.wikipedia.org/wiki/MAC_address */
    mac[0] &= 0xfe;
    mac[0] |= 0x02;
  } else {
    perror("Unable to open /dev/urandom");
    exit(3);
  }


  stop_dnsmasq();

  ofd = open(newleases, O_WRONLY|O_CREAT|O_EXCL, 0644);
  if (ofd == -1) {
    fprintf(stderr, "Unable to open %s exclusively.  "
	    "Either a rare collision occured and rerunning the previous "
	    "command will succeed, "
	    "or the file was abandoned in the middle of an atomic operation "
	    "and should be deleted.\n",
	    newleases);
    exit(1);
  }

  rv = fchmod(ofd, 0644);
  if (rv == -1) {
    perror(newleases);
    exit(18);
  }

  ifp = fopen(leases, "r");
  if (ifp) {
    while ((s = getline(&buffer, &bufsize, ifp)) > 0) {
      n=write(ofd, buffer, s);
      if (n != s) {
	fprintf(stderr, "short write to %s\n", newleases);
	perror(newleases);
	exit(4);
      }
      n=sscanf(buffer,"dhcp-host=%x:%x:%x:%x:%x:%x,%d.%d.%d.%d",
	       imac+0, imac+1, imac+2, imac+3, imac+4, imac+5,
	       iip+0, iip+1, iip+2, iip+3);
      if (n == 10) {
	if (iip[0]==IP0 && iip[1]==IP1 && iip[2]==IP2) {
	  used[iip[3]] = 1;
	}
	if (imac[0]==mac[0] && imac[1]==mac[1] && imac[2]==mac[2] &&
	    imac[3]==mac[3] && imac[4]==mac[4] && imac[5]==mac[5]) {
	  fprintf(stderr, "Rerun prior command.  A rare MAC address conflict "
		  "occured.");
	  exit(5);
	}
      }
    }
    free(buffer);
    rv = fclose(ifp);
    if (rv == -1) {
      perror(leases);
      exit(14);
    }
  }


  for (i=IP3LOW; i<=IP3HIGH; i++) {
    if (used[i] == 0) break;
  }
  if (i<=IP3HIGH) {
  } else {
    fprintf(stderr, "All available IPs in range %d.%d.%d.%d to %d.%d.%d.%d "
	    "used in %s.  Manual cleanup of orphaned addresses "
	    "without the commented PIDs running may be required.\n",
	    leases);
  }

  ip[0] = IP0;
  ip[1] = IP1;
  ip[2] = IP2;
  ip[3] = i;
 
  n = snprintf(outbuf, sizeof(outbuf),
	       "dhcp-host=%02x:%02x:%02x:%02x:%02x:%02x,%d.%d.%d.%d\n",
	       mac[0], mac[1], mac[2], mac[3], mac[4], mac[5],
	       ip[0], ip[1], ip[2], ip[3]);
  if (n>0 && n<sizeof(outbuf)) {
    time_t t;
    s = write(ofd, outbuf, n);

    t=time(NULL);
    fprintf(stderr,
       "%s: tunbr adding %x:%x:%x:%x:%x:%x %d.%d.%d.%d\n",
       ctime(&t),
       mac[0], mac[1], mac[2], mac[3], mac[4], mac[5],
       ip[0], ip[1], ip[2], ip[3]);

    if (s != n) {
      perror(newleases);
      exit(6);
    }
  } else {
    fprintf(stderr, "Unable to write buffer[] with new ethers entry.\n");
    exit(9);
  }

  rv = close(ofd);
  if (rv == -1) {
    perror(newleases);
    exit(7);
  }

  rv = rename(newleases, leases);
  if (rv == -1) {
    perror(newleases);
    exit(8);
  }

  start_dnsmasq();
}



/* A set of functions to return the names of environment variables
 * for each instance number. */
const char *macfile_var(int i) {
  static char buffer[32];
  int n;

  if (i<2) return "MACFILE";
  n = snprintf(buffer, sizeof(buffer), "MACFILE%d", i);
  if (n>0 && n<sizeof(buffer)-1) {
    return buffer;
  }
  return NULL;
}

const char *macaddr_var(int i) {
  static char buffer[32];
  int n;

  if (i<2) return "MACADDR";
  n = snprintf(buffer, sizeof(buffer), "MACADDR%d", i);
  if (n>0 && n<sizeof(buffer)-1) {
    return buffer;
  }
  return NULL;
}

const char *ipaddr_var(int i) {
  static char buffer[32];
  int n;

  if (i<2) return "IPADDR";
  n = snprintf(buffer, sizeof(buffer), "IPADDR%d", i);
  if (n>0 && n<sizeof(buffer)-1) {
    return buffer;
  }
  return NULL;
}

const char *iface_var(int i) {
  static char buffer[32];
  int n;

  if (i<2) return "IFACE";
  n = snprintf(buffer, sizeof(buffer), "IFACE%d", i);
  if (n>0 && n<sizeof(buffer)-1) {
    return buffer;
  }
  return NULL;
}


/* scan through the tunbr environment variables looking for the
 * next free instance.  The variables are:
 * MACADDRx, MACFILEx, IPADDRx, and IFACEx.  x is null for the first
 * instance and starts at 2 and above for the next.
 * Returns x as an integer. x=0 for null and x=-1 on error. */
int next_instance() {
  int i, n;
  char buffer[32];

  for (i=1;i<=MAX_INSTANCES;i++) {
    if (getenv(macfile_var(i))==NULL) return i;
  }
}


int main(int argc, char **argv) {
  uid_t uid;
  pid_t child;
  char command[256], device[16];
  int n, tapn, nuid, rv, status;
  FILE *tunctlfp;
  int rfd, mfd;
  char macfile[256], macaddr[20], ipaddr[16];
  unsigned char mac[6], ip[4];
  int instance;
  struct sigaction ignoresig;


  /* ignore most interrupt-like signals, let them fall through to
   * the child process, kill it, and then tunbr can clean up and exit */
  ignoresig.sa_handler = SIG_IGN;
  ignoresig.sa_flags = 0;
  sigemptyset(&ignoresig.sa_mask);
  sigaction(SIGHUP, &ignoresig, NULL);
  sigaction(SIGINT, &ignoresig, NULL);
  sigaction(SIGQUIT, &ignoresig, NULL);
  sigaction(SIGABRT, &ignoresig, NULL);
  sigaction(SIGALRM, &ignoresig, NULL);
  sigaction(SIGTERM, &ignoresig, NULL);
  sigaction(SIGUSR1, &ignoresig, NULL);
  sigaction(SIGUSR2, &ignoresig, NULL);


  instance = next_instance();
  if (instance<0) {
    fprintf(stderr, "Unable to find unallocated MACADDR variables\n");
    return -1;
  }


  add_to_leases(LEASES, NEWLEASES, mac, ip);

  n = snprintf(macfile, sizeof(macfile),
	       PXELINUXCFGDIR "01-%02x-%02x-%02x-%02x-%02x-%02x",
	       mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  mfd = creat(macfile,0644);
  if (mfd == -1) {
    perror(macfile);
    goto release_ether;
  }
  rv = close(mfd);
  if (rv == -1) {
    perror("close macfile fd");
    goto release_ether;
  }

  uid = getuid();
  rv = chown(macfile, uid, -1);
  if (rv == -1) {
    perror("chown");
    goto release_ether;
  }

  rv = chmod(macfile, 0644);
  if (rv == -1) {
    perror("chmod");
    return errno;
  }

  rv = setenv(macfile_var(instance), macfile, 1);
  if (rv == -1) {
    fprintf(stderr, "insufficient environment space for %s variable\n",
	    macfile_var(instance));
    goto release_ether;
  }


  n = snprintf(macaddr, sizeof(macaddr),
	       "%02x:%02x:%02x:%02x:%02x:%02x",
	       mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  rv = setenv(macaddr_var(instance), macaddr, 1);
  if (rv == -1) {
    fprintf(stderr, "insufficient environment space for %s variable\n",
	    macaddr_var(instance));
    goto release_ether;
  }


  n = snprintf(ipaddr, sizeof(ipaddr),
	       "%d.%d.%d.%d",
	       ip[0], ip[1], ip[2], ip[3]);
  rv = setenv(ipaddr_var(instance), ipaddr, 1);
  if (rv == -1) {
    fprintf(stderr, "insufficient environment space for %s variable\n",
	    ipaddr_var(instance));
    goto release_ether;
  }


  n = snprintf(command, sizeof(command), TUNCTL " -u %d", uid);
  tunctlfp = popen(command, "r");
  if (!tunctlfp) {
    perror(command);
    goto release_ether;
  }

  n = fscanf(tunctlfp, "Set 'tap%d' persistent and owned by uid %d",
             &tapn, &nuid);
  if (n != 2) {
    fprintf(stderr, "'%s' output did not provide a device and uid\n",
	    command);
    goto release_ether;
  }

  if (pclose(tunctlfp) == -1) {
    perror("tunctlfp close failed");
    goto release_iface;
  }


  n = snprintf(command, sizeof(command), BRCTL " addif " BRIDGE " tap%d",
               tapn);
  rv = system(command);
  if (rv == -1) {
    perror(TUNCTL);
    goto release_iface;
  }
  if (rv) {
    fprintf(stderr, "'%s' returned %d\n", command, rv);
    goto release_iface;
  }


  n = snprintf(command, sizeof(command), IFCONFIG " tap%d up", tapn);
  rv = system(command);
  if (rv == -1) {
    perror(TUNCTL);
    goto release_iface;
  }
  if (rv) {
    fprintf(stderr, "'%s' returned %d", command, rv);
    goto release_iface;
  }


  n = snprintf(device, sizeof(device), "tap%d", tapn);
  rv = setenv(iface_var(instance), device, 1);
  if (rv == -1) {
    fprintf(stderr, "insufficient environment space for %s variable\n",
	    iface_var(instance));
    goto release_iface;
  }


  child = fork();
  if (child>0) {
    pid_t p;
    time_t t=time(NULL);
    p = waitpid(child, &status, 0);
    fprintf(stderr, "%s: tunbr waitpid(%d)=%d, status=%d\n",
      ctime(&t), child, p, status);
  } else if (child==0) {
    setuid(uid);
    execvp(argv[1], argv+1);
    fprintf(stderr,"execvp(%s,...) failed: %s\n",
	    argv[1], strerror(errno));
    fprintf(stderr,"%s probably needs to be fully qualified.\n", argv[1]);
    exit(-1);
  } else {
    perror("fork");
  }


 release_iface:
  n = snprintf(command, sizeof(command), BRCTL " delif " BRIDGE " tap%d",
               tapn);
  rv = system(command);
  if (rv == -1) {
    perror(TUNCTL);
    goto release_ether;
  }
  if (rv) {
    fprintf(stderr, "'%s' returned %d\n", command, rv);
  }


  n = snprintf(command, sizeof(command), TUNCTL " -d tap%d", tapn);
  rv = system(command);
  if (rv == -1) {
    perror(TUNCTL);
  }
  if (rv) {
    fprintf(stderr, "'%s' returned %d\n", command, rv);
  }


 release_ether:
  del_from_leases(LEASES, NEWLEASES, mac, ip);


  rv = unlink(macfile);
  if (rv == -1) {
    perror("unlink");
    return errno;
  }


  return (WIFEXITED(status) ? WEXITSTATUS(status) : -1);
}
