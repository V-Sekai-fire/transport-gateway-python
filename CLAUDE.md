# transport-gateway-python

A second implementation of the reliable half of the fabric's WebTransport contract, on
`aioquic`. It exists to disagree with `transport-gateway-c` where one of them is wrong,
so anything that makes the two agree by construction destroys the only thing it produces.

`README.md` says what this is. Record decisions in the `multiplayer-fabric-manuals` repository.
`CITATION.cff` says what this repository is built on; add a reference there when you add a
dependency here.

## It is a second opinion, so it copies nothing

This is the rule the repository exists for, and it is the easy one to break under deadline.

- Do NOT copy a constant, a field offset, a packet size, or a framing rule out of
  `transport-gateway-c`, `datasource-queen/src/wt.c`, or the engine's `modules/http3`. Two
  copies of one number agree until one is edited, and an agreement reached by copying tests
  that somebody can copy.
- Do NOT relax a check so a cross-test passes. A disagreement is the output. Record it in
  `OPEN_GAPS.md` and find out which side is wrong.
- Do NOT read the specification off the C implementation. Read RFC 9114, RFC 9297, and the
  Lean sources in `contract-wt`, `contract-entity-packet` and `contract-connection-fsm`.
- `gen/` is emitted by `lake exe packet_emit` in `contract-entity-packet`. Regenerate those
  files, never edit them.

## It is a transport layer

It holds no authority, runs no simulation, and keeps no durable state. It also never learns
what a command means: a line arrives, it goes to the ring, and whatever comes back goes out.

Do NOT add a command table, a dispatch switch, or a reply format here. That is
`weft_interactor_t`'s side of the seam and `datasource-queen` already keeps it.

## The framing rule

There is none, in either direction. A WebTransport stream's FIN is the boundary and a datagram
is one message. A length prefix belongs to a byte stream, which is why `transport_tcp.c` has
one and this does not.

## It carries no player traffic

`transport-gateway-c` measured a scripting runtime at 5.70 M/s against a 15 M/s bar, and
117.8 ns per runtime crossing against a 66.7 ns per-packet budget. Those numbers are why policy
lives in an interactor rather than in the packet path, and they apply here in full.

Do NOT put this on a per-tick path, and do NOT quote a throughput number for it that
`data/measurements/` cannot produce.

## Build

```sh
pixi run check       # the conformance gate: 64 golden vectors, decode, re-encode, compare
pixi run selftest    # the same gate against corrupted input, which must fail
pixi run serve       # terminate WebTransport on localhost
```

The key may be EC or RSA. `aioquic` loads P-256, P-384 and RSA-2048 alike, which is why this
repository runs on it: `contract-wt` records the Godot demo server generating P-256, and the
stack this replaced accepted only RSA. `OPEN_GAPS.md` has the measurement.
