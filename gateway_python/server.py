"""Terminate the reliable half of the fabric's WebTransport contract, on pywebtransport.

One line of ASCII arrives on a bidirectional stream, goes to the ring, and whatever the
interactor answers goes back out on the same stream. Neither direction carries a length prefix:
a WebTransport stream's FIN is already the boundary, which is why `transport_tcp.c` needs a
four-byte prefix and this does not.

This never learns what a command means. That belongs to `weft_interactor_t` on the other side
of the ring, and `datasource-queen` already keeps that split.

    python -m gateway_python.server --cert cert.pem --key key.pem --port 4433

SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from pywebtransport import ServerApp, ServerConfig, WebTransportSession

from gateway_python.bus import Bus

# The path the Extended CONNECT names. `datasource-queen` answers on /ward and this is the same
# session, reached by a second implementation.
WT_PATH = "/ward"

# A command line, capped where the interactor caps it. WARD_COMMAND_MAX is 512 in
# datasource-queen's interactor.h, and a longer line is dropped rather than truncated: half a
# command is a different command.
COMMAND_MAX = 512

_log = logging.getLogger("transport-gateway-python")


async def serve_session(session: WebTransportSession, bus: Bus, *, poll: float = 0.001) -> None:
    """Carry one session's streams until it closes."""
    _log.info("session open path=%s id=%s", session.path, session.session_id)

    async for stream in session.incoming_bidirectional_streams():
        line = await stream.readline()
        if len(line) > COMMAND_MAX:
            _log.warning("command of %d bytes dropped, cap is %d", len(line), COMMAND_MAX)
            await stream.close()
            continue

        bus.publish(line.strip())

        reply = None
        while reply is None:
            reply = bus.receive()
            if reply is None:
                await asyncio.sleep(poll)

        await stream.write_all(data=reply, end_stream=True)


def build(*, cert: str, key: str, host: str, port: int, publish_to: str, subscribe_to: str) -> ServerApp:
    app = ServerApp(config=ServerConfig(bind_host=host, bind_port=port, certfile=cert, keyfile=key))
    bus = Bus(publish_to=publish_to, subscribe_to=subscribe_to)

    @app.route(path=WT_PATH)
    async def _handler(session: WebTransportSession) -> None:
        await serve_session(session, bus)

    return app


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cert", required=True, help="PEM certificate. The key must be RSA; see OPEN_GAPS.md")
    ap.add_argument("--key", required=True, help="PEM private key, RSA")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=4433)
    ap.add_argument("--publish-to", default="fabric/transport/gateway-python/command")
    ap.add_argument("--subscribe-to", default="fabric/transport/gateway-python/reply")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    app = build(
        cert=args.cert,
        key=args.key,
        host=args.host,
        port=args.port,
        publish_to=args.publish_to,
        subscribe_to=args.subscribe_to,
    )
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
