#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "config.h"

int main(int argc, char **argv) {
  // cd into a newly created directory so that modules in the CWD
  // can't affect execution
  char tmpdir[40] = "/tmp/debmarshal.tmp.XXXXXX";
  if (!mkdtemp(tmpdir)) {
    perror("debmarshpriv");
    exit(1);
  }
  if (-1 == chdir(tmpdir)) {
    perror("debmarshpriv");
    exit(1);
  }
  if (-1 == rmdir(tmpdir)) {
    perror("debmarshpriv");
    exit(1);
  }

  // argc + 4 because we're adding 4 arguments, removing argv[0], and
  // allocating space for the NULL at the end
  char **new_argv = malloc(sizeof(char *) * (argc + 4));
  if (!new_argv) {
    perror("debmarshpriv");
    exit(1);
  }

  new_argv[0] = "python";
  // Ignore all environment variables that can affect the interpreter
  // (e.g. PYTHONPATH)
  new_argv[1] = "-E";
  new_argv[2] = "-m";
  new_argv[3] = "debmarshal.privops";
  // Skip argv[0], because we don't want to pass that along
  //
  // Also, argv[argc] is already NULL, so we'll just copy that over
  memcpy(new_argv + 4, argv + 1, sizeof(char *) * argc);

  if (execv(PYTHON, new_argv)) {
    perror("debmarshpriv");
    exit(1);
  }

  return 0;
}
