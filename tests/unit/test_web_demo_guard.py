import socket

import pytest


def test_demo_socket_guard_denies_external_even_if_provider_configuration_regresses(monkeypatch):
    from research.docs.agent_engineering_upgrade.s1_web_upgrade.demo import install_network_guard

    calls = []
    monkeypatch.setattr(socket.socket, "connect", lambda sock, address: calls.append(address))
    monkeypatch.setattr(socket.socket, "connect_ex", lambda sock, address: calls.append(address))
    install_network_guard()
    with socket.socket() as sock:
        with pytest.raises(OSError, match="forbids external"):
            sock.connect(("api.deepseek.com", 443))
        with pytest.raises(OSError, match="forbids external"):
            sock.connect_ex(("8.8.8.8", 443))
        sock.connect(("127.0.0.1", 1))
    assert calls == [("127.0.0.1", 1)]
