import atexit
import signal
from concurrent.futures import ThreadPoolExecutor

shared_executor = ThreadPoolExecutor()


@atexit.register
def cleanup_executor():
    shared_executor.shutdown(wait=True)  # Gracefully shut down the thread pool


def shutdown_executor(signum, frame):
    cleanup_executor()


# Register signal handlers for explicit cleanup
signal.signal(signal.SIGINT, shutdown_executor)
signal.signal(signal.SIGTERM, shutdown_executor)
