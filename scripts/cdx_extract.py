#!/usr/bin/env python3
"""
Extract every capture of one MIME type (e.g. all PDFs) from a WARC file,
using its index to find them instead of reading the whole WARC file. The WARC
file can be local, or on the web (fetching only the matching records).

The index says, for every capture, its MIME type and where its record is
(WARC file name, byte offset, length). So the index is filtered first, and
then only the matching records are read from the WARC file. The same works
with any index that has those fields, such as a Parquet index queried with
DuckDB or pandas.

Things to keep in mind:
  - The MIME type is what the server claimed, which can be wrong. Some indexes,
    like the End of Term Archive ones, also have the type detected from the
    content ("mime-detected"); it is used when present, and disagreements are
    reported. Otherwise, the payload is checked against the file signature for
    a few known types, and mismatches are skipped (but files mislabeled the
    other way, e.g. a PDF sent as application/octet-stream, are missed).
  - URLs make poor file names: they are long, may have characters that are
    not allowed in file names, and the same URL may be captured many times.
    Files are named TIMESTAMP-URL-DIGEST.ext: readable, sorted by time, and
    unique (the digest is a hash of the content).

Usage:
    python cdx_extract.py INDEX.cdx MIME OUTDIR [WARC_DIR]

    e.g. python cdx_extract.py FILE.cdxj.gz application/pdf pdfs/

WARC_DIR is as in cdx_lookup.py: a local directory (default: the index file's
directory), or a URL, e.g. https://eotarchive.s3.amazonaws.com/
"""

import mimetypes
import os
import re
import sys
from io import BytesIO

from warcio.archiveiterator import ArchiveIterator

from cdx_lookup import parse_index, read_range, warc_location

# The first bytes ("magic numbers") that files of some types start with.
SIGNATURES = {
    "application/pdf": b"%PDF-",
    "image/png": b"\x89PNG",
    "image/jpeg": b"\xff\xd8\xff",
    "image/gif": b"GIF8",
}


def read_payload(location, offset, length):
    """Read the payload of the record at the given offset in a WARC file."""
    data = read_range(location, offset, length)
    record = next(ArchiveIterator(BytesIO(data)))
    return record.content_stream().read()


def file_name(entry, mime):
    """A file name that is readable, sortable, safe, and unique."""
    url = entry["url"].split("://", 1)[-1]
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", url)[:80].strip("_")
    digest = entry.get("digest", entry["offset"]).split(":")[-1][:8]  # drop "sha1:"
    ext = mimetypes.guess_extension(mime) or ".bin"
    return f"{entry['timestamp']}-{slug}-{digest}{ext}"


def main(index_path, mime, out_dir, warc_dir=None):
    warc_dir = warc_dir or os.path.dirname(index_path)
    os.makedirs(out_dir, exist_ok=True)
    saved = 0

    for entry in parse_index(index_path):
        declared = entry.get("mime")
        detected = entry.get("mime-detected")
        if (detected or declared) != mime or entry.get("status") != "200":
            continue
        if detected and detected != declared:
            print(f"NOTE {entry['url']}: server said {declared}, detected {detected}",
                  file=sys.stderr)

        location = warc_location(entry["filename"], warc_dir)
        payload = read_payload(location, int(entry["offset"]), int(entry["length"]))

        signature = SIGNATURES.get(mime)
        if signature and not payload[:1024].lstrip().startswith(signature):
            print(f"SKIP {entry['url']}: labeled {mime} but starts with {payload[:16]!r}",
                  file=sys.stderr)
            continue

        out_path = os.path.join(out_dir, file_name(entry, mime))
        with open(out_path, "wb") as f:
            f.write(payload)
        print(f"{out_path}\t{entry['url']}")
        saved += 1

    print(f"\nSaved {saved} file(s) to {out_dir}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        sys.exit(__doc__)
    main(*sys.argv[1:])
