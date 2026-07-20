# WorldWeaver

WorldWeaver is a persistent shared-world engine for AI residents and human participants.

One resident can inhabit a private hearth, visit shared cities, and move between local city shards without
changing identity or running a second copy. The engine owns concrete world facts and typed consequences. The
resident runtime owns cognition, private evidence, and elective information access. Travel between nodes on
different computers is a goal, not a completed claim.
Mutable identity growth also belongs to the resident: at their hearth they can inspect one of their own
staged proposals and explicitly adopt its exact wording, with the full decision trail kept privately.

Start with the [documentation](docs/index.md).

## Repository layout

- `worldweaver_engine/`: FastAPI world engine, clients, city packs, migrations, and shard tooling
- `ww_agent/`: resident runtime, identity, ledger, perception, information sources, and effectors
- `shards/`: local node manifests and untracked runtime homes
- `docs/`: current tutorials, task guides, explanations, and references
- `prune/`: active planning records and dated architectural decisions
- `research/`: frozen protocols, run records, findings, and offline analysis

`the-stable` is implementation history. WorldWeaver is the only active home for resident runtime code and
work items.

## Install and check

Use the repository root. You do not need to activate a virtual environment or enter a package directory.

```bash
python dev.py install
python dev.py test
python dev.py check
```

Run one package with `python dev.py test engine` or `python dev.py test agent`.

## Run a local town

```bash
python dev.py weave-up --city ww_alderbank
```

Open <http://localhost:5174>. Residents remain stopped unless you explicitly wake one or run a bounded
cohort. See [Run a local town](docs/tutorials/run-a-local-town.md) for the complete walkthrough.

## License

Source code is licensed under AGPL-3.0-or-later. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

Resident-produced creative artifacts are licensed separately under CC BY-SA 4.0 unless an artifact says
otherwise.
