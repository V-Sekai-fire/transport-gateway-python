# transport-gateway-python

A second implementation of the reliable half of the fabric's WebTransport contract, on a QUIC stack that shares no code with the first.

## What it is for

It terminates control streams and passes each command line to the ring and the reply back, holding no authority and no durable state. Its output is agreement or disagreement with `transport-gateway-c`: where the two disagree, one of them is wrong about the contract. `gen/` is vendored from `contract-entity-packet`; regenerate it, never edit it.

## Build and run

```sh
pixi run check
pixi run selftest
```

`pixi run check` runs the conformance gate against the golden vectors, and `pixi run selftest` shows it failing on purpose.

## Licence

MIT; see `LICENSE`.
