#!/usr/bin/env python3
"""Validate the static publishing boundary, then copy only approved assets."""

import argparse
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path

ASSETS = {"index.html", "styles.css", "counter.js", "app.js"}
POLICY = {
    "default-src": ["'none'"],
    "script-src": ["'self'"],
    "style-src": ["'self'"],
    "img-src": ["'self'", "data:"],
    "connect-src": ["'none'"],
    "base-uri": ["'none'"],
    "form-action": ["'none'"],
    "object-src": ["'none'"],
}
SECURITY_PRELUDE = [
    '<!doctype html>',
    '<html lang="ja">',
    '<head>',
    '<meta charset="utf-8">',
    '<meta http-equiv="Content-Security-Policy" content="'
    + "; ".join(key + " " + " ".join(values) for key, values in POLICY.items()) + '">',
    '<meta name="referrer" content="no-referrer">',
]


class PagePolicy(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.policies = 0
        self.referrer = False
        self.scripts = []
        self.in_script = False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if len(attrs) != len(attributes):
            raise ValueError("Duplicate HTML attributes are not allowed")
        if any(name.startswith("on") or name in {"style", "srcdoc"} for name in attrs):
            raise ValueError("Inline handlers, styles and documents are not allowed")
        if tag in {"base", "iframe", "object", "embed", "form", "style", "template"}:
            raise ValueError(f"Unsupported active HTML element: {tag}")
        if tag == "meta" and attrs.get("http-equiv", "").lower() == "content-security-policy":
            directives = [part.split() for part in attrs.get("content", "").split(";") if part.strip()]
            policy = {part[0]: part[1:] for part in directives}
            if len(policy) != len(directives) or policy != POLICY:
                raise ValueError("Content Security Policy differs from the security baseline")
            self.policies += 1
        if tag == "meta" and attrs.get("name") == "referrer":
            self.referrer = attrs.get("content") == "no-referrer"
        if tag in {"script", "link"} and self.policies != 1:
            raise ValueError("Security policy must precede all resource loads")
        if tag == "script":
            src = attrs.get("src")
            if src not in {"./counter.js", "./app.js"} or "defer" not in attrs:
                raise ValueError("Only the approved local deferred scripts are allowed")
            self.scripts.append(src)
            self.in_script = True
        for name in {"src", "href", "xlink:href", "srcset", "action", "formaction"} & attrs.keys():
            value = attrs[name] or ""
            if value.startswith("#"):
                continue
            if tag == "script" and name == "src" and value in {"./counter.js", "./app.js"}:
                continue
            if tag == "link" and name == "href":
                if attrs.get("rel") == "stylesheet" and value == "./styles.css":
                    continue
                if attrs.get("rel") == "icon" and value.startswith("data:image/svg+xml,%3Csvg"):
                    continue
            raise ValueError(f"Unapproved resource reference in {tag}.{name}")

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False

    def handle_data(self, data):
        if self.in_script and data.strip():
            raise ValueError("Inline scripts are not allowed")


def validate_site(source: Path) -> None:
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Site source must be a real directory")
    if {item.name for item in source.iterdir()} != ASSETS:
        raise ValueError("dist must contain exactly the four approved public assets")
    for name in ASSETS:
        path = source / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Public asset must be a regular file: {name}")
    html = (source / "index.html").read_text(encoding="utf-8")
    # HTMLParser is not an HTML5 parser. Require an exact approved prelude
    # (allowing only whitespace between elements) so inert/invalid placement
    # cannot masquerade as an effective CSP. Changes here require review.
    # Python's \s also accepts NBSP, which HTML treats as body text.
    html_whitespace = r"[ \t\r\n\f]*"
    prefix = r"\A" + html_whitespace + html_whitespace.join(re.escape(line) for line in SECURITY_PRELUDE)
    if not re.match(prefix, html):
        raise ValueError("The approved document security prelude must come first")
    page = PagePolicy()
    page.feed(html)
    page.close()
    if page.policies != 1 or not page.referrer:
        raise ValueError("One CSP and a no-referrer policy are required")
    if page.scripts != ["./counter.js", "./app.js"]:
        raise ValueError("Counter and app scripts must load exactly once in order")


def build_site(source: Path, destination: Path) -> None:
    validate_site(source)
    # Refuse existing output, including broken symlinks, rather than publishing stale data.
    destination.mkdir(parents=True, exist_ok=False)
    for name in sorted(ASSETS):
        shutil.copyfile(source / name, destination / name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("dist"))
    parser.add_argument("--output", type=Path, default=Path("_site"))
    args = parser.parse_args()
    build_site(args.source, args.output)
    print("Validated and staged exactly four public assets.")
