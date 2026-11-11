"""Run acceptance commands with no paid keys and no external socket connections."""

import os
import runpy
import socket
import sys


def main():
    os.environ.update(
        DEEPSEEK_API_KEY="",
        EMBEDDING_API_KEY="",
        LANGSMITH_API_KEY="",
        EXPERIENCE_MEMORY_MODE="off",
        LANGCHAIN_TRACING_V2="false",
        LANGSMITH_TRACING="false",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
    )
    for key in list(os.environ):
        if key.lower().endswith("_proxy"):
            os.environ.pop(key)
    original, original_ex = socket.socket.connect, socket.socket.connect_ex

    def check(address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1", "localhost"}:
            raise OSError("P4-E acceptance forbids external network/paid dispatch")

    def connect(sock, address):
        check(address)
        return original(sock, address)

    def connect_ex(sock, address):
        check(address)
        return original_ex(sock, address)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    module = sys.argv[1]
    sys.argv = sys.argv[1:]
    runpy.run_module(module, run_name="__main__")


if __name__ == "__main__":
    main()
