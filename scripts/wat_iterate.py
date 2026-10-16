#!/usr/bin/env python3
"""
Iterate over the records in a WAT file and print metadata about each capture.

A WAT file is itself a WARC file, derived from an original WARC. For every
record in the original WARC there is a "metadata" record whose content is a
JSON document describing it, without the payload itself. Its structure is:

    Container                  where the original record lives
      Filename, Offset           (original WARC file name and byte offset)
    Envelope
      WARC-Header-Metadata       the original record's WARC headers
      Payload-Metadata
        HTTP-Response-Metadata   (only for HTTP responses)
          Response-Message         status line: Version, Status, Reason
          Headers                  HTTP response headers
          HTML-Metadata            (only for HTML pages)
            Head                     Title, meta tags, ...
            Links                    every link found on the page

This is the tier to use for link graphs and metadata analysis at a fraction
of the size of the original WARC.

Usage:
    python wat_iterate.py FILE.warc.wat.gz

Output (tab-separated): original WARC-Type, HTTP status, number of links,
URI, page title
"""

import json
import sys

from warcio.archiveiterator import ArchiveIterator


def main(path):
    with open(path, "rb") as stream:
        for record in ArchiveIterator(stream):
            # The first record is a "warcinfo" describing the file; skip it.
            if record.rec_type != "metadata":
                continue

            data = json.load(record.content_stream())
            envelope = data["Envelope"]

            warc_headers = envelope["WARC-Header-Metadata"]
            orig_type = warc_headers.get("WARC-Type")
            uri = warc_headers.get("WARC-Target-URI", "-")

            # Most of the interesting fields are optional, depending on the
            # type of the original record, so walk down with .get() and {}.
            http = envelope.get("Payload-Metadata", {}).get("HTTP-Response-Metadata", {})
            status = http.get("Response-Message", {}).get("Status", "-")
            html = http.get("HTML-Metadata", {})
            title = html.get("Head", {}).get("Title", "-")
            links = html.get("Links", [])

            # Titles may contain tabs or newlines; flatten them for display.
            title = " ".join(title.split())

            print(orig_type, status, len(links), uri, title, sep="\t")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
