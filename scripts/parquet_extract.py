#!/usr/bin/env python3
"""
Find captures of one MIME type from one site in a Parquet index, and save them
as files, fetching only those records from the WARC files on the web.

A Parquet index has the same information as a CDX index, but stored by
column, with the URL already split into parts (host, domain, path, ...). So
it can be queried with SQL, and a query only reads the columns it needs.
DuckDB can query it right from its URL, without downloading it.

The End of Term 2024 Archive Parquet index is split into the same shards as
its ZipNum index (see zipnum_lookup.py): eot24-cdx-00021.parquet has the
captures in eot24-cdx-00021.cdxj.gz. Querying a single shard takes under a
minute; to find which shard has a site, look up its URL key in
cluster.summary, e.g.

    grep -m1 '^gov,fema)' cluster.summary

Usage:
    python parquet_extract.py PARQUET DOMAIN MIME OUTDIR [LIMIT]

    PARQUET  a Parquet file path or URL, e.g.
             https://eotarchive.s3.amazonaws.com/eot-index/table/eot-main/crawl=EOT-2024/eot24-cdx-00021.parquet
    DOMAIN   the registered domain, e.g. fema.gov (includes all its hosts)
    MIME     the detected MIME type, e.g. application/pdf
    OUTDIR   where to save the files
    LIMIT    how many to save at most (default: 10)

Requires DuckDB (pip install duckdb).
"""

import os
import sys

import duckdb

from cdx_extract import file_name, read_payload
from cdx_lookup import warc_location

EOT_WARCS = "https://eotarchive.s3.amazonaws.com/"

QUERY = """
    SELECT url, strftime(fetch_time, '%Y%m%d%H%M%S') AS timestamp,
           content_mime_type, content_digest,
           warc_filename, warc_record_offset, warc_record_length
    FROM read_parquet($parquet)
    WHERE url_host_registered_domain = $domain
      AND content_mime_detected = $mime
      AND fetch_status = 200
    LIMIT $limit
"""


def main(parquet, domain, mime, out_dir, limit=10):
    params = {"parquet": parquet, "domain": domain, "mime": mime, "limit": int(limit)}
    rows = duckdb.execute(QUERY, params).fetchall()
    print(f"Found {len(rows)} capture(s)", file=sys.stderr)

    os.makedirs(out_dir, exist_ok=True)
    for url, timestamp, declared, digest, filename, offset, length in rows:
        if declared != mime:
            print(f"NOTE {url}: server said {declared}, detected {mime}", file=sys.stderr)

        payload = read_payload(warc_location(filename, EOT_WARCS), offset, length)

        entry = {"url": url, "timestamp": timestamp, "digest": digest, "offset": str(offset)}
        out_path = os.path.join(out_dir, file_name(entry, mime))
        with open(out_path, "wb") as f:
            f.write(payload)
        print(f"{out_path}\t{url}")


if __name__ == "__main__":
    if len(sys.argv) not in (5, 6):
        sys.exit(__doc__)
    main(*sys.argv[1:])
