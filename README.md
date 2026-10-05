# transport-gateway-python

A second implementation of the reliable half of the fabric's WebTransport contract, on a QUIC stack that shares no code with the first.

## What it is for

It terminates control streams and passes each command line to the ring and the reply back, holding no authority and no durable state. Its output is agreement or disagreement with `transport-gateway-c`: where the two disagree, one of them is wrong about the contract. `gen/` is vendored from `contract-entity-packet`; regenerate it, never edit it.

## Build and run

```sh
pixi run check
pixi run selftest
pixi run serve
```

`pixi run check` runs the conformance gate against the golden vectors, and `pixi run selftest` shows it failing on purpose. `pixi run serve` starts the gateway and needs a `cert.pem` and `key.pem` in the working directory.

## Licence

MIT; see `LICENSE`.
