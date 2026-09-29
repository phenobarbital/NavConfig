"""Check static documentation links and Python snippet syntax without dependencies."""

import ast
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Page(HTMLParser):
    """Collect local link targets and executable Python examples."""

    def __init__(self, path: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.errors: list[str] = []
        self.snippets: list[str] = []
        self._python = False
        self._code: list[str] = []
        self.feed(path.read_text(encoding="utf-8"))
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if identifier := attributes.get("id"):
            if identifier in self.ids:
                self.errors.append(f"duplicate id: {identifier}")
            self.ids.add(identifier)
        for key in ("href", "src"):
            if target := attributes.get(key):
                self.links.append(target)
        if (
            tag == "code"
            and "language-python" in (attributes.get("class") or "").split()
        ):
            self._python = True
            self._code = []

    def handle_data(self, data: str) -> None:
        if self._python:
            self._code.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "code" and self._python:
            self.snippets.append("".join(self._code))
            self._python = False


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "site"
    pages = {path.resolve(): Page(path) for path in sorted(root.rglob("*.html"))}
    errors: list[str] = []
    if root / "index.html" not in pages:
        errors.append("site/index.html is missing")
    for path, page in pages.items():
        label = path.relative_to(root)
        errors.extend(f"{label}: {error}" for error in page.errors)
        for snippet in page.snippets:
            try:
                ast.parse(snippet)
            except SyntaxError as error:
                errors.append(f"{label}: invalid Python example: {error}")
        for link in page.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            if url.path.startswith("/"):
                errors.append(f"{label}: use a project-relative URL: {link}")
                continue
            target = (path.parent / unquote(url.path)).resolve() if url.path else path
            if not target.is_relative_to(root):
                errors.append(f"{label}: link escapes the published site: {link}")
                continue
            if target.is_dir():
                target /= "index.html"
            if not target.is_file():
                errors.append(f"{label}: missing target: {link}")
            elif url.fragment and target in pages:
                if unquote(url.fragment) not in pages[target].ids:
                    errors.append(f"{label}: missing fragment: {link}")
    if errors:
        print("\n".join(errors))
        return 1
    snippets = sum(len(page.snippets) for page in pages.values())
    print(
        f"Checked {len(pages)} HTML pages: local links, IDs and {snippets} Python snippets OK."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
