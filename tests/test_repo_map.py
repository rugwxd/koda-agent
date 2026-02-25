"""Tests for the repository map builder."""

from src.code.repo_map import RepoMapBuilder


class TestRepoMapBuilder:
    def test_build_from_directory(self, tmp_path):
        # Create a mini repo
        (tmp_path / "main.py").write_text(
            "from helper import do_thing\n\ndef main():\n    do_thing()\n"
        )
        (tmp_path / "helper.py").write_text("def do_thing():\n    return 42\n")

        builder = RepoMapBuilder()
        repo_map = builder.build(tmp_path)
        assert repo_map.total_files == 2
        assert repo_map.total_symbols > 0

    def test_render_map(self, tmp_path):
        (tmp_path / "app.py").write_text("def start():\n    pass\n")
        builder = RepoMapBuilder()
        repo_map = builder.build(tmp_path)
        rendered = repo_map.render(max_tokens=500)
        assert "Repository Map" in rendered
        assert "app.py" in rendered

    def test_skips_hidden_dirs(self, tmp_path):
        (tmp_path / ".hidden").mkdir()
        (tmp_path / ".hidden" / "secret.py").write_text("x = 1\n")
        (tmp_path / "visible.py").write_text("y = 2\n")

        builder = RepoMapBuilder()
        repo_map = builder.build(tmp_path)
        paths = [e.path for e in repo_map.entries]
        assert not any(".hidden" in p for p in paths)

    def test_empty_directory(self, tmp_path):
        builder = RepoMapBuilder()
        repo_map = builder.build(tmp_path)
        assert repo_map.total_files == 0

    def test_reference_ranking(self, tmp_path):
        # helper.py should rank higher because it's imported
        (tmp_path / "main.py").write_text("from helper import run\n\ndef main():\n    run()\n")
        (tmp_path / "helper.py").write_text("def run():\n    return 1\n")
        (tmp_path / "unused.py").write_text("def unused():\n    pass\n")

        builder = RepoMapBuilder()
        repo_map = builder.build(tmp_path)

        scores = {e.path: e.reference_score for e in repo_map.entries}
        assert scores.get("helper.py", 0) > scores.get("unused.py", 0)
