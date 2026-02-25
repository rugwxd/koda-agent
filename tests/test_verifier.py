"""Tests for the automated code verifier."""

from src.config import CriticConfig
from src.critic.verifier import CheckStatus, Verifier


class TestVerifier:
    def test_ast_check_valid(self, sample_python_file):
        config = CriticConfig(ast_check=True, run_lint=False, run_tests=False)
        verifier = Verifier(config=config)
        result = verifier.verify([str(sample_python_file)])
        assert result.passed
        ast_checks = [c for c in result.checks if "ast_check" in c.check_name]
        assert len(ast_checks) == 1
        assert ast_checks[0].status == CheckStatus.PASSED

    def test_ast_check_invalid(self, tmp_path):
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(\n  return 1\n")
        config = CriticConfig(ast_check=True, run_lint=False, run_tests=False)
        verifier = Verifier(config=config)
        result = verifier.verify([str(bad_file)])
        assert not result.passed
        assert len(result.errors) > 0

    def test_all_checks_disabled(self, sample_python_file):
        config = CriticConfig(ast_check=False, run_lint=False, run_tests=False)
        verifier = Verifier(config=config)
        result = verifier.verify([str(sample_python_file)])
        assert result.passed
        assert all(c.status == CheckStatus.SKIPPED for c in result.checks)

    def test_non_python_files_skipped(self, tmp_path):
        txt_file = tmp_path / "readme.txt"
        txt_file.write_text("hello")
        config = CriticConfig(ast_check=True, run_lint=False, run_tests=False)
        verifier = Verifier(config=config)
        result = verifier.verify([str(txt_file)])
        assert result.passed

    def test_summary(self, sample_python_file):
        config = CriticConfig(ast_check=True, run_lint=False, run_tests=False)
        verifier = Verifier(config=config)
        result = verifier.verify([str(sample_python_file)])
        summary = result.summary
        assert "OK" in summary
