# SPDX-License-Identifier: Apache-2.0
"""Bounded canonical-CBOR LAN transport. Signatures authenticate, no encryption."""
import socket
import struct
from tools.verification_profile import codec as c
MAX=900000

def exact(sock,n):
    out=bytearray()
    while len(out)<n:
        chunk=sock.recv(n-len(out))
        if not chunk:raise ConnectionError('incomplete S2 frame')
        out.extend(chunk)
    return bytes(out)
def receive(sock):
    n=struct.unpack('!I',exact(sock,4))[0];c.need(0<n<=MAX,'frame limit');return exact(sock,n)
def send(sock,raw):
    c.need(type(raw) is bytes and 0<len(raw)<=MAX,'frame limit');sock.sendall(struct.pack('!I',len(raw))+raw)
def rpc(host,port,raw):
    with socket.create_connection((host,port),timeout=10) as sock:
        sock.settimeout(20);send(sock,raw);return receive(sock)
