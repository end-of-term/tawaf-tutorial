#!/usr/bin/env python3
"""
Show the anatomy of a single WARC response record, layer by layer.

    +--------------------------+
    | WARC headers             |  added by the crawler: what, when, where from
    +--------------------------+
    | HTTP status + headers    |  sent by the web server, stored as received
    +--------------------------+
    | payload                  |  the actual resource: HTML, image, PDF, ...
    +--------------------------+

Keep in mind that HTTP headers are only what the server claimed; e.g. the
Content-Type may not match the payload. (The End of Term Archive META files
record the detected type; see warc_metadata.py.)

Usage:
    python warc_record.py FILE.warc.gz [URL]

Shows the first response record in the file, or the first one for URL.
"""

import sys

from warcio.archiveiterator import ArchiveIterator

PREVIEW_BYTES = 500


def main(path, url=None):
    with open(path, "rb") as stream:
        for record in ArchiveIterator(stream):
            if record.rec_type != "response":
                continue
            if url and record.rec_headers.get_header("WARC-Target-URI") != url:
                continue

            print("=== WARC headers ===")
            print(record.rec_headers.to_str())

            print("=== HTTP headers ===")
            print(record.http_headers.to_str())

            # content_stream() undoes any HTTP transfer and content encoding
            # (chunked, gzip, ...), giving the payload as the browser saw it.
            # raw_stream would give the bytes exactly as they are stored.
            payload = record.content_stream().read()
            print(f"=== Payload ({len(payload)} bytes, first {PREVIEW_BYTES} shown) ===")
            print(payload[:PREVIEW_BYTES].decode("utf-8", errors="replace"))
            return

    sys.exit(f"No response record found{' for ' + url if url else ''}")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    main(*sys.argv[1:])
