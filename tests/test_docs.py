import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
HTML_PATH = ROOT / "docs/index.html"
HTML = HTML_PATH.read_text(encoding="utf-8")
CSS = (ROOT / "docs/style.css").read_text(encoding="utf-8")


def test_public_site_uses_canonical_repository_slug():
    assert "pretrained-tb-afb-detection-engine" not in HTML
    canonical = re.search(r'<link rel="canonical" href="([^"]+)"', HTML)
    assert canonical
    assert canonical.group(1) == (
        "https://abusuraihsakhri.github.io/pretrained-tb-afb-detection-model/"
    )


def test_public_site_has_social_and_icon_metadata():
    required = (
        'property="og:title"',
        'property="og:description"',
        'property="og:url"',
        'property="og:image"',
        'name="twitter:card"',
        'rel="apple-touch-icon"',
        'name="theme-color"',
    )
    for marker in required:
        assert marker in HTML
    for asset in ("og-card.png", "favicon.svg", "favicon-32.png", "apple-touch-icon.png"):
        assert (ROOT / "docs" / asset).is_file()


def test_public_site_local_assets_exist():
    for attribute, value in re.findall(r'\b(href|src)="([^"]+)"', HTML):
        if value.startswith(("http://", "https://", "#")):
            continue
        target = (HTML_PATH.parent / value.split("?", 1)[0].split("#", 1)[0]).resolve()
        assert target.is_relative_to(HTML_PATH.parent.resolve())
        assert target.is_file(), f"Missing local {attribute} asset: {value}"


def test_public_site_accessibility_contract():
    assert 'class="skip-link"' in HTML
    assert 'aria-controls="primary-navigation"' in HTML
    assert 'aria-expanded="false"' in HTML
    assert '<caption>' in HTML
    assert 'scope="col"' in HTML
    assert 'scope="row"' in HTML
    assert ':focus-visible' in CSS
    assert '@media (prefers-reduced-motion: no-preference)' in CSS
    headings = [int(level) for level in re.findall(r"<h([1-6])\b", HTML)]
    assert headings[0] == 1
    assert all(current - previous <= 1 for previous, current in zip(headings, headings[1:]))


def test_public_site_is_model_focused_and_avoids_unsupported_claims():
    lowered = HTML.lower()
    assert "yolov8n" in lowered
    assert "deep-learning model" in lowered
    assert "research use only" in lowered
    for internal_term in ("data audited", "dataset audit", "validation hold", "quarantined"):
        assert internal_term not in lowered
    prohibited = (
        "clinical-grade",
        "ready for immediate clinical",
        "reducing pathologist screening time",
        "cfr part 11 audit",
        "fully trained &amp; verified",
    )
    for claim in prohibited:
        assert claim not in lowered
