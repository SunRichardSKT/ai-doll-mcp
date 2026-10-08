"""Hidden collector entry point for Windows login startup and manual launch."""
import contextlib
import logging
import logging.handlers
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


class LogStream:
    def __init__(self, logger):
        self.logger = logger
        self.pending = ''

    def write(self, value):
        self.pending += value
        while '\n' in self.pending:
            line, self.pending = self.pending.split('\n', 1)
            if line.strip():
                self.logger.info(line.rstrip())
        # Bound unfinished lines from external code as well as the rotated files.
        if len(self.pending) > 4096:
            self.logger.info(self.pending[:4096])
            self.pending = ''
        return len(value)

    def flush(self):
        if self.pending:
            self.logger.info(self.pending)
            self.pending = ''


def main():
    folder = ROOT/'build/device-lab'
    folder.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('ai-doll-background')
    logger.setLevel(logging.INFO)
    logger.propagate = False  # MCP libraries can install root handlers using stderr.
    # Open the shared rotating log only after the OS lease has been acquired.
    from service_lifecycle import ServiceLease, ServiceAlreadyRunning
    try:
        with ServiceLease(folder/'companion.lock'):
            handler = logging.handlers.RotatingFileHandler(folder/'background-service.log',
                        maxBytes=524288, backupCount=2, encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
            logger.addHandler(handler)
            stream = LogStream(logger)
            try:
                with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                    import device_setup_server
                    device_setup_server.run_service()
            except Exception:
                logger.exception('Companion stopped unexpectedly')
                return 1
            finally:
                stream.flush()
                handler.close()
    except ServiceAlreadyRunning:
        return 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
