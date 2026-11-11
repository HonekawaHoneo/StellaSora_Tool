import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts/build-site.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class SiteBuildTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "dist"
        shutil.copytree(ROOT / "dist", self.source)

    def change_html(self, before, after):
        page = self.source / "index.html"
        text = page.read_text()
        self.assertIn(before, text)
        page.write_text(text.replace(before, after))

    def test_build_copies_only_the_four_public_assets(self):
        (self.root / ".env").write_text("PRIVATE_PLACEHOLDER=example")
        output = self.root / "output"
        builder.build_site(self.source, output)
        self.assertEqual(sorted(p.name for p in output.iterdir()),
                         ["app.js", "counter.js", "index.html", "styles.css"])
        for asset in output.iterdir():
            self.assertEqual(asset.read_bytes(), (self.source / asset.name).read_bytes())

    def test_hidden_files_and_subdirectories_fail_closed(self):
        for name in [".env", "unexpected.js", "private"]:
            with self.subTest(name=name):
                path = self.source / name
                path.mkdir() if name == "private" else path.write_text("example")
                with self.assertRaises(ValueError):
                    builder.validate_site(self.source)
                path.rmdir() if path.is_dir() else path.unlink()

    def test_symlink_cannot_publish_a_file_outside_dist(self):
        asset = self.source / "app.js"
        asset.unlink()
        asset.symlink_to(ROOT / "dist/app.js")
        with self.assertRaises(ValueError):
            builder.validate_site(self.source)

    def test_missing_or_weakened_csp_is_rejected(self):
        self.change_html("script-src 'self'", "script-src 'self' 'unsafe-inline'")
        with self.assertRaises(ValueError):
            builder.validate_site(self.source)
        self.change_html("Content-Security-Policy", "disabled-policy")
        with self.assertRaises(ValueError):
            builder.validate_site(self.source)

    def test_remote_script_and_inline_event_handler_are_rejected(self):
        self.change_html('src="./app.js"', 'src="https://example.invalid/app.js"')
        with self.assertRaises(ValueError):
            builder.validate_site(self.source)
        self.change_html('src="https://example.invalid/app.js"', 'src="./app.js"')
        self.change_html("<body>", '<body onload="alert(1)">')
        with self.assertRaises(ValueError):
            builder.validate_site(self.source)

    def test_csp_must_be_effective_in_the_document_head(self):
        page = self.source / "index.html"
        original = page.read_text()
        csp = next(line for line in original.splitlines() if "Content-Security-Policy" in line)
        variants = [
            original.replace(csp, "<template>" + csp + "</template>"),
            original.replace(csp, "").replace("<body>", "<body>" + csp),
            original.replace(csp, "<div>" + csp + "</div>"),
            original.replace(csp, "<title>" + csp + "</title>"),
            original.replace(csp, "unexpected head text" + csp),
            original.replace("<head>", "<div></div><head>"),
            original.replace("<head>", "unexpected text<head>"),
            original.replace(csp, "<title/>" + csp),
            *[original.replace(csp, tag + csp) for tag in ["</body>", "</html>", "</br>"]],
            "\u00a0" + original,
            original.replace(csp, "\u00a0" + csp),
        ]
        for index, variant in enumerate(variants):
            with self.subTest(case=index):
                page.write_text(variant)
                with self.assertRaises(ValueError):
                    builder.validate_site(self.source)

    def test_inline_script_and_resource_before_csp_are_rejected(self):
        self.change_html("</head>", "<script>alert(1)</script></head>")
        with self.assertRaises(ValueError):
            builder.validate_site(self.source)
        self.change_html("<script>alert(1)</script></head>", "</head>")
        self.change_html('<meta charset="utf-8">',
                         '<meta charset="utf-8"><script defer src="./app.js"></script>')
        with self.assertRaises(ValueError):
            builder.validate_site(self.source)

    def test_stale_or_symlinked_output_is_not_reused(self):
        output = self.root / "output"
        output.mkdir()
        (output / ".env").write_text("example")
        with self.assertRaises(FileExistsError):
            builder.build_site(self.source, output)
        output_link = self.root / "output-link"
        output_link.symlink_to(output, target_is_directory=True)
        with self.assertRaises(FileExistsError):
            builder.build_site(self.source, output_link)


if __name__ == "__main__":
    unittest.main()
