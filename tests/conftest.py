import socket

import pytest


@pytest.fixture(autouse=True)
def disable_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Core tests must not access the network")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
