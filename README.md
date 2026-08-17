# transport-gateway-python

Control streams, terminated a second time, on a stack that shares nothing with the first.

A **transport layer** is the input that triggers an interactor. This one holds no authority,
runs no simulation, keeps no durable state, and carries no player traffic either. What it
produces is agreement or disagreement with `transport-gateway-c`.

## Why the fabric wants two

`transport-gateway-c`, `transport-ingest-c` and the engine's `modules/http3` all vendor
picoquic and picotls, so both ends of every session run the same code. RFD 0088 chose that, and
it buys interoperability by construction while giving up the check. A wire implemented once
describes the program that implements it, and nothing establishes that the specification is
implementable from the specification. Khronos ratifies against two implementations for this.

`pywebtransport` shares no line of code with picoquic: its QUIC core is Rust. Where the two
disagree, one of them is wrong about the contract.

## What it terminates

An HTTP/3 Extended CONNECT, then the reliable half of RFD 0049 — one line of ASCII in, the
interactor's bytes back out. Neither direction carries a length prefix, because a WebTransport
stream's FIN already is the boundary.

It never learns what a command means. The line goes to the ring and the reply comes back, which
is the `weft_transport_t` split `datasource-queen` already keeps.

## The wire is not ours to define

`gen/` is emitted by `lake exe packet_emit` in `contract-entity-packet` and vendored here, the
way `transport-asset` vendors its rebac tables. Regenerate those files, never edit them, and
carry no field offset or packet size anywhere else.

## State

The conformance gate runs: 64 golden vectors decode, re-encode and compare byte for byte, with
`pixi run selftest` showing the gate fail on purpose. The live cross-test against
`transport-gateway-c` is not written.
