import importlib.util
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("update_hosts", Path(__file__).resolve().parents[1] / "scripts/update_hosts.py")
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


class GeneratorTests(unittest.TestCase):
    def generate(self, source, exceptions):
        # Small fixtures exercise the production parser and transformation; production keeps its size guard.
        original = generator.validate_size
        with patch.object(generator, "validate_size", side_effect=lambda text: original(text, minimum=1)):
            return generator.generate(source, exceptions)

    def test_exact_matches_preserve_other_aliases_comments_and_subdomains(self):
        source = "# credits\n0.0.0.0 allow.example keep.example # source note\n0.0.0.0 sub.allow.example\n:: allow.example\n"
        output = self.generate(source, ["allow.example"])
        self.assertEqual(generator.blocked_domains(output), {"keep.example", "sub.allow.example"})
        self.assertIn("# credits\n", output)
        self.assertIn("source note", output)
        self.assertIn("# :: allow.example", output)

    def test_case_insensitive_match_and_missing_exception_are_safe(self):
        output = self.generate("0.0.0.0 ALLOW.EXAMPLE\n0.0.0.0 keep.example\n", ["allow.example", "absent.example"])
        self.assertEqual(generator.blocked_domains(output), {"keep.example"})

    def test_deterministic_output_and_preserved_existing_comments(self):
        source = "# 0.0.0.0 allow.example\n0.0.0.0 keep.example\n"
        self.assertEqual(self.generate(source, ["allow.example"]), source)

    def test_upstream_underscore_dns_labels_are_preserved(self):
        source = "0.0.0.0 philadelphia_cbslocal.us.intellitxt.com\n"
        self.assertEqual(self.generate(source, ["allow.example"]), source)

    def test_invalid_or_html_input_is_rejected(self):
        for source in ("<html>error</html>", "not-an-ip bad.example", "0.0.0.0", "0.0.0.0 *.example"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.generate(source, ["allow.example"])

    def test_empty_small_and_suspicious_changes_are_rejected(self):
        previous = "".join(f"0.0.0.0 a{i}.example\n" for i in range(100))
        with self.assertRaises(ValueError):
            generator.validate_size("")
        with self.assertRaises(ValueError):
            generator.validate_size(previous)
        for size in (79, 151):
            candidate = "".join(f"0.0.0.0 a{i}.example\n" for i in range(size))
            with self.subTest(size=size), self.assertRaises(ValueError):
                generator.validate_size(candidate, previous, minimum=1)

    def test_invalid_and_duplicate_exceptions_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "exceptions.txt"
            for contents in ("", "*.example\n", "Upper.example\n", "a.example\na.example\n"):
                path.write_text(contents)
                with self.subTest(contents=contents), self.assertRaises(ValueError):
                    generator.load_exceptions(path)

    def test_atomic_write_preserves_mode_and_noop_mtime(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hosts"
            path.write_bytes(b"before")
            path.chmod(0o640)
            generator.write_changed(path, b"after")
            self.assertEqual(path.read_bytes(), b"after")
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)
            before = path.stat().st_mtime_ns
            generator.write_changed(path, b"after")
            self.assertEqual(path.stat().st_mtime_ns, before)

    def test_readme_requires_unique_marker_pairs(self):
        with self.assertRaises(ValueError):
            generator.update_section("no markers", "exceptions", "data")

    def test_size_override_requires_an_explicit_commit(self):
        with patch.object(sys, "argv", ["update_hosts.py", "--accept-size-change"]), self.assertRaises(SystemExit):
            generator.main()

    def test_invalid_download_leaves_existing_files_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial = {"hosts": "0.0.0.0 keep.example\n", "README.md": "existing documentation\n", "exceptions.txt": "allow.example\n"}
            for name, data in initial.items():
                (root / name).write_text(data)
            with patch.object(generator, "ROOT", root), patch.object(generator, "fetch", return_value=b"<html>gateway error</html>"), patch.object(sys, "argv", ["update_hosts.py", "--upstream-commit", "a" * 40]), self.assertRaises(ValueError):
                generator.main()
            for name, data in initial.items():
                self.assertEqual((root / name).read_text(), data)
            self.assertFalse((root / "source.json").exists())


if __name__ == "__main__":
    unittest.main()
