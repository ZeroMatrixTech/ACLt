# SPDX-License-Identifier: Apache-2.0
"""Stateless relay: no credential, signing key, local grant or contribution cache."""
from protocol import exchange


class Gateway:
    def __init__(self, host, port, timeout=5):
        self.host, self.port, self.timeout = host, port, timeout

    def handle(self, message):
        return exchange(self.host, self.port, message, self.timeout)
