import pytest
from vesper.commands.run import run_app


def test_framework_missing_dist_exits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "vesper.toml").write_text('[project]\ntemplate = "react"\n', encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        run_app()

    assert exc.value.code == 1


def test_framework_missing_dist_message(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "vesper.toml").write_text('[project]\ntemplate = "react"\n', encoding="utf-8")

    with pytest.raises(SystemExit):
        run_app()

    assert "vesper build" in capsys.readouterr().out


def test_vue_missing_dist_exits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "vesper.toml").write_text('[project]\ntemplate = "vue"\n', encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        run_app()

    assert exc.value.code == 1


def test_svelte_missing_dist_exits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "vesper.toml").write_text('[project]\ntemplate = "svelte"\n', encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        run_app()

    assert exc.value.code == 1


def test_vanilla_missing_dist_proceeds_to_entrypoint_check(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "vesper.toml").write_text('[project]\ntemplate = "vanilla"\n', encoding="utf-8")

    with pytest.raises(SystemExit):
        run_app()

    out = capsys.readouterr().out
    assert "vesper build" not in out
    assert "entrypoint" in out.lower()


def test_no_toml_vanilla_default_proceeds_to_entrypoint_check(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit):
        run_app()

    out = capsys.readouterr().out
    assert "vesper build" not in out
    assert "entrypoint" in out.lower()


def test_framework_with_dist_proceeds_to_entrypoint_check(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "vesper.toml").write_text('[project]\ntemplate = "react"\n', encoding="utf-8")
    (tmp_path / "dist").mkdir()

    with pytest.raises(SystemExit):
        run_app()

    out = capsys.readouterr().out
    assert "vesper build" not in out
    assert "entrypoint" in out.lower()
