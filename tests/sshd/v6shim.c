#define _GNU_SOURCE
#include <dlfcn.h>
#include <sys/socket.h>
#include <netinet/in.h>
/* Tests only: a kernel without IPv6 (gVisor) - pam_radius 2.0 wants an IPv6
   socket even for an IPv4 server. Given a UDP socket of another family that
   binds to nothing. */
static int fake[1024];
int socket(int d, int t, int p) {
  int (*real)(int, int, int) = dlsym(RTLD_NEXT, "socket");
  if (d == AF_INET6) { int fd = real(AF_UNIX, SOCK_DGRAM, 0); if (fd >= 0 && fd < 1024) fake[fd] = 1; return fd; }
  return real(d, t, p);
}
int bind(int fd, const struct sockaddr *a, socklen_t l) {
  int (*real)(int, const struct sockaddr *, socklen_t) = dlsym(RTLD_NEXT, "bind");
  if (fd >= 0 && fd < 1024 && fake[fd]) return 0;
  return real(fd, a, l);
}
