from __future__ import annotations

from src.familiar.file_scope import FileScope


def _tree(tmp_path):
    (tmp_path / "notes.md").write_text("hello, this is fine to read", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET_KEY=hunter2", encoding="utf-8")
    (tmp_path / "config.key").write_text("-----BEGIN KEY-----", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("build/\n*.log\n", encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out.txt").write_text("artifact", encoding="utf-8")
    (tmp_path / "run.log").write_text("logs", encoding="utf-8")
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "main.py").write_text("print('hi')", encoding="utf-8")
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "token.txt").write_text("abc", encoding="utf-8")
    return FileScope(read_roots=[tmp_path])


def test_reads_normal_files(tmp_path):
    fs = _tree(tmp_path)
    assert fs.read("notes.md")["ok"] is True
    assert "fine to read" in fs.read("notes.md")["content"]
    assert fs.read("src/main.py")["ok"] is True


def test_default_deny_hides_secrets_even_without_gitignore(tmp_path):
    fs = _tree(tmp_path)
    assert fs.read(".env") == {"ok": False, "reason": "ignored"} or fs.read(".env")["reason"] == "ignored"
    assert fs.read("config.key")["ok"] is False  # *.key
    assert fs.read("secrets/token.txt")["ok"] is False  # *secret* dir


def test_gitignore_is_respected(tmp_path):
    fs = _tree(tmp_path)
    assert fs.read("run.log")["ok"] is False  # *.log
    assert fs.read("build/out.txt")["ok"] is False  # build/ dir-only pattern hides contents


def test_cannot_escape_the_root(tmp_path):
    fs = _tree(tmp_path)
    assert fs.read("/etc/passwd")["reason"] == "outside_scope"
    assert fs.read("../../../../etc/passwd")["reason"] == "outside_scope"
    assert fs.read("src/../../../../etc/hosts")["reason"] == "outside_scope"


def test_tree_and_listdir_omit_hidden(tmp_path):
    fs = _tree(tmp_path)
    tree = fs.tree(max_depth=3, max_entries=100)
    assert "notes.md" in tree and "src/main.py" in tree
    assert not any(".env" in t or "build" in t or ".log" in t or "secrets" in t for t in tree)
    names = [e["name"] for e in fs.listdir()["entries"]]
    assert "notes.md" in names and ".env" not in names and "secrets" not in names


def test_multi_root_qualifies_paths_and_resolves_them(tmp_path):
    # two roots → entries are root-qualified ("alpha/notes.md") so the listing is legible
    # and each qualified path round-trips back through read(); a single root stays bare.
    a = tmp_path / "alpha"; a.mkdir()
    b = tmp_path / "beta"; b.mkdir()
    (a / "notes.md").write_text("from alpha", encoding="utf-8")
    (b / "notes.md").write_text("from beta", encoding="utf-8")
    fs = FileScope(read_roots=[a, b])
    tree = fs.tree(max_depth=1, max_entries=50)
    assert "alpha/notes.md" in tree and "beta/notes.md" in tree
    # the root name disambiguates two same-named files
    assert fs.read("alpha/notes.md")["content"] == "from alpha"
    assert fs.read("beta/notes.md")["content"] == "from beta"
    # read echoes the qualified path so the hint, the typed path, and the echo all agree
    assert fs.read("beta/notes.md")["path"] == "beta/notes.md"


def test_single_root_stays_unqualified(tmp_path):
    # one root → no prefix, identical to pre-multi-root behavior
    (tmp_path / "notes.md").write_text("solo", encoding="utf-8")
    fs = FileScope(read_roots=[tmp_path])
    assert "notes.md" in fs.tree(max_depth=1, max_entries=10)
    assert fs.read("notes.md")["path"] == "notes.md"


def test_multi_root_still_refuses_escape_and_secrets(tmp_path):
    a = tmp_path / "alpha"; a.mkdir()
    b = tmp_path / "beta"; b.mkdir()
    (b / ".env").write_text("SECRET=x", encoding="utf-8")
    fs = FileScope(read_roots=[a, b])
    assert fs.read("beta/.env")["ok"] is False  # default-deny holds across roots
    assert fs.read("../../../etc/passwd")["reason"] == "outside_scope"
