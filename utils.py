import os
import sys
import traceback

def system(command):
    '''
    Forks a command and disowns it.
    '''

    if os.fork() != 0:
        return

    try:
        # Child.
        os.setsid()     # Become session leader.
        if os.fork() != 0:
            os._exit(0)

        os.chdir(os.path.expanduser('~'))
        os.umask(0)

        # Close all file descriptors.
        import resource
        maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
        if maxfd == resource.RLIM_INFINITY:
            maxfd = 1024
        for fd in range(maxfd):
            try:
                os.close(fd)
            except OSError:
                pass

        # Open /dev/null for stdin, stdout, stderr.
        os.open('/dev/null', os.O_RDWR)
        os.dup2(0, 1)
        os.dup2(0, 2)

        os.execve(command[0], command, os.environ)
    except:
        try:
            # Error in child process.
            sys.stderr.write('Error in child process: ')
            traceback.print_exc()
        except:
            pass
        sys.exit(1)
