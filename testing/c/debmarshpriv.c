#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "config.h"

int main(int argc, char **argv) {
  // argc + 3 because we're adding 3 arguments, removing argv[0], and
  // allocating space for the NULL at the end
  char **new_argv = malloc(sizeof(char *) * (argc + 3));
  if (!new_argv) {
    perror("debmarshpriv");
    exit(1);
  }
  new_argv[0] = "python";
  new_argv[1] = "-m";
  new_argv[2] = "debmarshal.privops";

  // Skip argv[0], because we don't want to pass that along
  //
  // Also, argv[argc] is already NULL, so we'll just copy that over
  memcpy(new_argv + 3, argv + 1, sizeof(char *) * argc);
  if (execv(PYTHON, new_argv)) {
    perror("debmarshpriv");
    exit(1);
  }

  return 0;
}
