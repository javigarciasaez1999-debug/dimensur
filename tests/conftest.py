import socket

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Ningún test puede contactar Google, OpenAI ni la API de publicación."""
    def blocked(*args, **kwargs):
        raise AssertionError("Red bloqueada durante las pruebas")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
