import argparse
import json

from scripts import resident_cohort


def test_event_reader_returns_only_named_structural_json(tmp_path):
    path = tmp_path / "resident.log"
    path.write_text(
        "private-looking runtime text that must be ignored\n" + json.dumps({"event": "resident_tick", "tick": 1}) + "\n" + json.dumps({"event": "resident_run_summary", "resident": "riley", "ticks": 4}) + "\n",
        encoding="utf-8",
    )

    assert resident_cohort._event_from_log(path, "resident_run_summary") == {
        "event": "resident_run_summary",
        "resident": "riley",
        "ticks": 4,
    }


def test_complete_cohort_always_runs_named_cleanup(tmp_path, monkeypatch):
    homes = [tmp_path / "avram", tmp_path / "sal"]
    for home in homes:
        home.mkdir()
    output_dir = tmp_path / "run"
    parked = []

    monkeypatch.setattr(resident_cohort, "_preflight", lambda *_args: (True, "ready"))
    monkeypatch.setattr(resident_cohort, "_sample_presence", lambda *_args: None)
    monkeypatch.setattr(
        resident_cohort,
        "_park",
        lambda home, _server: parked.append(home.name) or (True, "parked"),
    )

    class FinishedProcess:
        returncode = 0

        def __init__(self, command, **kwargs):
            resident = command[command.index("--home") + 1].split("/")[-1]
            kwargs["stdout"].write(
                json.dumps(
                    {
                        "event": "resident_run_summary",
                        "resident": resident,
                        "ticks": 3,
                        "prompt_tokens": 10,
                    }
                )
                + "\n"
            )
            kwargs["stdout"].flush()

        def poll(self):
            return 0

    monkeypatch.setattr(resident_cohort.subprocess, "Popen", FinishedProcess)

    args = argparse.Namespace(
        home=[str(home) for home in homes],
        server_url="http://example.test",
        wake=True,
        duration=60.0,
        model=None,
        temperature=None,
        action_tendency=True,
        stagger=0.0,
        output_dir=str(output_dir),
        city="ww_test",
    )

    assert resident_cohort._run(args) == 0
    assert parked == ["avram", "sal"]
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "complete"
    assert set(summary["residents"]) == {"avram", "sal"}
    assert summary["residents"]["avram"]["prompt_tokens"] == 10


def test_presence_sampling_counts_only_named_resident_overlap(tmp_path, monkeypatch):
    homes = [tmp_path / "avram", tmp_path / "sal"]
    report = resident_cohort._new_presence_report(homes)
    payload = {
        "roster": [
            {"session_id": "avram-123", "location": "Commons Bank"},
            {"session_id": "sal-456", "location": "Commons Bank"},
            {"session_id": "human-session", "location": "Commons Bank"},
        ],
        "timeline": [{"summary": "prose is not part of this report"}],
    }

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr(resident_cohort.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())

    resident_cohort._sample_presence("http://example.test", homes, report)
    finalized = resident_cohort._finalize_presence(report)

    assert finalized["samples_with_colocation"] == 1
    assert finalized["max_colocated_residents"] == 2
    assert finalized["colocation_pairs"] == {"avram|sal": 1}
    assert finalized["locations_seen"] == {
        "avram": ["Commons Bank"],
        "sal": ["Commons Bank"],
    }
