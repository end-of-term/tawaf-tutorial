#!/usr/bin/env python3
"""
Extract the outlinks of every page in a WAT file, the edges of a link graph.

Each WAT record lists the links found in an HTML page, as they appear in it:

    {"path": "A@/href",  "url": "/about.html", "text": "About us"}
    {"path": "IMG@/src", "url": "logo.png"}

"path" says where the link was found (element@/attribute). "url" is the
attribute value as written, so it has to be normalized the way a browser
would: tabs, newlines, and surrounding spaces removed, resolved against the
page's URL (or its <base href>) if relative, and the #fragment dropped. Empty
links, and links that are not http(s), such as mailto: or javascript:, are
skipped.

Things to keep in mind:
  - Only HTML pages have links in WAT; PDFs and other documents do not.
  - Both internal (same host) and external links are included, as are
    embeds such as images and scripts; filter on "path" for A@/href to keep
    only navigational links.
  - Pages that add links with JavaScript may have fewer links than expected.

Usage:
    python wat_links.py FILE.warc.wat.gz

Output (tab-separated): source page, path, link as written, normalized link,
internal/external. A summary goes to stderr.
"""

import json
import sys
from collections import Counter
from urllib.parse import urldefrag, urljoin, urlsplit

from warcio.archiveiterator import ArchiveIterator

# Links as written may contain tabs and newlines. Browsers ignore them, so
# they are removed for normalizing, and escaped for showing the link as written.
REMOVE_WHITESPACE = str.maketrans("", "", "\t\n\r")
ESCAPES = str.maketrans({"\t": "\\t", "\n": "\\n", "\r": "\\r"})


def host(url):
    """The hostname without a leading "www.", to compare sites."""
    name = urlsplit(url).hostname or ""
    return name.removeprefix("www.")


def main(path):
    summary = Counter()
    with open(path, "rb") as stream:
        for record in ArchiveIterator(stream):
            if record.rec_type != "metadata":
                continue

            envelope = json.load(record.content_stream())["Envelope"]
            page = envelope["WARC-Header-Metadata"].get("WARC-Target-URI")
            http = envelope.get("Payload-Metadata", {}).get("HTTP-Response-Metadata", {})
            html = http.get("HTML-Metadata", {})
            if not html.get("Links"):
                continue
            summary["pages"] += 1

            # Relative links resolve against <base href> if the page has one.
            base = urljoin(page, html.get("Head", {}).get("Base", ""))

            for link in html["Links"]:
                raw = link.get("url", "")
                cleaned = raw.translate(REMOVE_WHITESPACE).strip()
                absolute = urldefrag(urljoin(base, cleaned)).url
                if not cleaned or urlsplit(absolute).scheme not in ("http", "https"):
                    summary["skipped"] += 1
                    continue

                kind = "internal" if host(absolute) == host(page) else "external"
                summary[kind] += 1
                print(page, link.get("path"), raw.translate(ESCAPES), absolute, kind, sep="\t")

    print(
        f"\n{summary['pages']} pages with links: {summary['internal']} internal, "
        f"{summary['external']} external, {summary['skipped']} skipped",
        file=sys.stderr,
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
