import socket

from . import settings


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((settings.FREE_PORT_HOST, settings.FREE_PORT_EPHEMERAL_PORT))

        return sock.getsockname()[1]
