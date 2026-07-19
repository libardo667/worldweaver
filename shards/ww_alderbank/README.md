# Alderbank development shard

`ww_alderbank` hosts the original fictional Alderbank pack on local port `8004`. It is a small private test
town for understandable objects, access, exchange, making, stoops, and other opt-in game consequences.

The tracked directory contains reproducible node scaffolding. Its `.env`, copied pack and rules data,
Postgres volume, resident hearths, and live world history are local machine state.

Current checkpoint:

- 13 connected schematic places;
- a bounded object stoop at Alderbank Commons;
- two replenishing, non-essential material pools at Alderbank Workshop;
- constructive game rules with harmful stakes disabled;
- working human entry through the public client;
- a four-resident cohort used for bounded runtime checks;
- federation discovery through the local directory node.

Start the town without residents:

```bash
python dev.py weave-up --city ww_alderbank
```

Wake residents deliberately with the commands in
[`docs/how-to/run-residents.md`](../../docs/how-to/run-residents.md). Their private runtime data is not a
test fixture and should not be inspected by ordinary automated tests.
