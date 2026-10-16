#!/usr/bin/env python3
"""
Iterate over the records in a WET file and print the extracted plain text.

A WET file is itself a WARC file, derived from an original WARC. Each HTML
(or other textual) capture is reduced to its visible text and stored as a
"conversion" record:
  - WARC-Target-URI  the URL of the original capture
  - WARC-Refers-To   the record ID of the original response in the WARC
  - content block    the extracted plain text (Content-Type: text/plain)

This is the tier to use for text analysis (search, NLP, language models)
without dealing with HTML or HTTP.

Usage:
    python wet_iterate.py FILE.warc.wet.gz

Output: for each capture, the URL, the text length, and a short text preview
"""

import sys

from warcio.archiveiterator import ArchiveIterator

PREVIEW_CHARS = 200


def main(path):
    with open(path, "rb") as stream:
        for record in ArchiveIterator(stream):
            # The first record is a "warcinfo" describing the file; skip it.
            if record.rec_type != "conversion":
                continue

            uri = record.rec_headers.get_header("WARC-Target-URI")
            refers_to = record.rec_headers.get_header("WARC-Refers-To")
            text = record.content_stream().read().decode("utf-8", errors="replace")

            # Collapse whitespace so the preview fits on one line.
            preview = " ".join(text.split())[:PREVIEW_CHARS]

            print(f"{uri}  ({len(text)} chars)")
            print(f"    from WARC record {refers_to}")
            print(f"    {preview}")
            print()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
