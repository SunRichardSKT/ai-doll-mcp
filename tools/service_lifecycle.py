"""Operating-system leases and exclusive loopback sockets for the collector."""
import os
import pathlib
import socket
from http.server import ThreadingHTTPServer


class ServiceAlreadyRunning(RuntimeError):
    pass


class ServiceLease:
    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.file = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open('a+b')
        try:
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise ServiceAlreadyRunning('The companion service is already running for this project') from None
        self.file = handle
        return self

    def __exit__(self, *args):
        if self.file:
            self.file.close()  # OS releases the lock, including after a crash.
            self.file = None


class ExclusiveLoopbackServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()
