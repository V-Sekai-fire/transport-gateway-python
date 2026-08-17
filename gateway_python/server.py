"""Terminate the reliable half of the fabric's WebTransport contract, on aioquic.

One line of ASCII arrives on a WebTransport stream, goes to the ring, and whatever the
interactor answers goes back out on the same stream. Neither direction carries a length prefix:
a WebTransport stream's FIN is already the boundary, which is why `transport_tcp.c` needs a
four-byte prefix and this does not.

This never learns what a command means. That belongs to `weft_interactor_t` on the other side
of the ring, and `datasource-queen` already keeps that split.

aioquic rather than picoquic is the whole point. Its QUIC and its TLS 1.3 are its own, written
in Python from the RFCs, so where this and `transport-gateway-c` disagree one of them is wrong
about the contract rather than both being wrong together.

    python -m gateway_python.server --cert cert.pem --key key.pem --port 4433

SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import H3Event, HeadersReceived, WebTransportStreamDataReceived
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import ProtocolNegotiated, QuicEvent

from gateway_python.bus import Bus

# The path the Extended CONNECT names. `datasource-queen` answers on /ward and this is the same
# session, reached by a second implementation.
WT_PATH = "/ward"

# A command line, capped where the interactor caps it. WARD_COMMAND_MAX is 512 in
# datasource-queen's interactor.h, and a longer line is dropped rather than truncated: half a
# command is a different command.
COMMAND_MAX = 512

# How often the reply poll asks the ring. The ring is shared memory and a poll is cheap, and
# RFD 0096 measured a busy-polled ring failing outright on a one-vCPU machine, so this sleeps
# rather than spins.
POLL_SECONDS = 0.001

_log = logging.getLogger("transport-gateway-python")


class WardProtocol(QuicConnectionProtocol):
    """One QUIC connection, carrying one WebTransport session's control streams."""

    def __init__(self, *args: object, bus: Bus, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._bus = bus
        self._http: H3Connection | None = None
        self._session_id: int | None = None
        self._partial: dict[int, bytearray] = {}

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, ProtocolNegotiated):
            self._http = H3Connection(self._quic, enable_webtransport=True)
        if self._http is None:
            return
        for h3_event in self._http.handle_event(event):
            self._h3_event_received(h3_event)

    def _h3_event_received(self, event: H3Event) -> None:
        assert self._http is not None

        if isinstance(event, HeadersReceived):
            headers = dict(event.headers)
            if headers.get(b":method") == b"CONNECT" and headers.get(b":protocol") == b"webtransport":
                path = headers.get(b":path", b"").decode(errors="replace")
                if path != WT_PATH:
                    # A session on a path nobody serves is refused rather than answered, so a
                    # client learns it reached the wrong door instead of waiting on silence.
                    self._http.send_headers(stream_id=event.stream_id, headers=[(b":status", b"404")])
                    self.transmit()
                    return
                self._session_id = event.stream_id
                _log.info("session open path=%s id=%d", path, event.stream_id)
                self._http.send_headers(
                    stream_id=event.stream_id,
                    headers=[(b":status", b"200"), (b"sec-webtransport-http3-draft", b"draft02")],
                )
                self.transmit()

        elif isinstance(event, WebTransportStreamDataReceived):
            buffered = self._partial.setdefault(event.stream_id, bytearray())
            buffered.extend(event.data)
            if event.stream_ended:
                self._partial.pop(event.stream_id, None)
                asyncio.ensure_future(self._answer(event.stream_id, bytes(buffered)))

    async def _answer(self, stream_id: int, command: bytes) -> None:
        """Hand one command to the ring and write back whatever answers it."""
        line = command.strip()
        if len(line) > COMMAND_MAX:
            _log.warning("command of %d bytes dropped, cap is %d", len(line), COMMAND_MAX)
            self._quic.send_stream_data(stream_id, b"", end_stream=True)
            self.transmit()
            return

        self._bus.publish(line)

        reply = None
        while reply is None:
            reply = self._bus.receive()
            if reply is None:
                await asyncio.sleep(POLL_SECONDS)

        self._quic.send_stream_data(stream_id, reply, end_stream=True)
        self.transmit()


def build_configuration(*, cert: str, key: str) -> QuicConfiguration:
    """aioquic loads an EC key as readily as an RSA one, which is why this repository runs on it.

    `OPEN_GAPS.md` records the measurement: P-256, P-384 and RSA-2048 all open a listener here,
    where the previous stack accepted only RSA while `contract-wt` records the Godot demo server
    generating P-256.
    """
    configuration = QuicConfiguration(is_client=False, alpn_protocols=H3_ALPN, max_datagram_frame_size=65536)
    configuration.load_cert_chain(cert, key)
    return configuration


async def run(*, cert: str, key: str, host: str, port: int, publish_to: str, subscribe_to: str) -> None:
    bus = Bus(publish_to=publish_to, subscribe_to=subscribe_to)
    await serve(
        host,
        port,
        configuration=build_configuration(cert=cert, key=key),
        create_protocol=lambda *a, **kw: WardProtocol(*a, bus=bus, **kw),
    )
    _log.info("listening on %s:%d%s", host, port, WT_PATH)
    await asyncio.Future()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cert", required=True, help="PEM certificate")
    ap.add_argument("--key", required=True, help="PEM private key. EC or RSA; both work")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=4433)
    ap.add_argument("--publish-to", default="fabric/transport/gateway-python/command")
    ap.add_argument("--subscribe-to", default="fabric/transport/gateway-python/reply")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(
        run(
            cert=args.cert,
            key=args.key,
            host=args.host,
            port=args.port,
            publish_to=args.publish_to,
            subscribe_to=args.subscribe_to,
        )
    )


if __name__ == "__main__":
    main()
