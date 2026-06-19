#!/usr/bin/env python3
"""
test_an_legislature_15_17_dyn_pagination.py

Verifies that Legislature XV–XVII PDF URLs are discoverable through the
dyn/ paginated index at:
  /dyn/{leg}/comptes-rendus/seance?page=N&limit=100

Why this test exists:
    From Legislature XV (2017) onward, the AN uses a modern paginated
    interface to list debate PDFs. The old /{leg}/cri/ pattern stopped
    working. This new dyn/ system was discovered through the public AN
    site navigation and verified by probing the ?page= parameter.

    Key insight: the default page size (limit=20) requires many page loads.
    Using limit=100 significantly reduces the number of requests.

What this test does:
    1. Fetches the first page of the dyn/ index for each legislature (15, 16, 17).
    2. Confirms it returns debate PDF links.
    3. Samples the first 3 PDF URLs and verifies they resolve to real content.
"""

import re
import requests
from lxml import html

requests.packages.urllib3.disable_warnings()

BASE = "https://www.assemblee-nationale.fr"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FrenchParliamentaryCorpus/1.0)"}

LEGISLATURES = [15, 16, 17]


def test_dyn_index_accessible():
    """Test that the dyn/ index API is accessible for each legislature."""
    for leg in LEGISLATURES:
        url = f"{BASE}/dyn/{leg}/comptes-rendus/seance?page=1&limit=20"
        r = requests.get(url, verify=False, timeout=20, headers=HEADERS)
        assert r.status_code == 200, f"Legislature {leg} dyn/ index returned {r.status_code}"
        print(f"  ✅ Legislature {leg}: {r.status_code}")


def test_dyn_index_contains_pdf_links():
    """Test that the dyn/ index contains valid session PDF links."""
    for leg in LEGISLATURES:
        url = f"{BASE}/dyn/{leg}/comptes-rendus/seance?page=1&limit=20"
        r = requests.get(url, verify=False, timeout=20, headers=HEADERS)
        assert r.status_code == 200

        tree = html.fromstring(r.content)
        links = tree.xpath("//a/@href")
        pdfs = list(dict.fromkeys(
            l for l in links
            if re.match(r'/dyn/\d+/comptes-rendus/seance/session-', l)
            and l.endswith('.pdf')
        ))

        assert len(pdfs) > 0, f"No PDF links found for legislature {leg}"
        print(f"  ✅ Legislature {leg}: {len(pdfs)} PDF links on page 1")


def test_dyn_pdfs_are_valid():
    """Test that sampled dyn/ PDF URLs resolve to real PDF content."""
    for leg in LEGISLATURES:
        url = f"{BASE}/dyn/{leg}/comptes-rendus/seance?page=1&limit=20"
        r = requests.get(url, verify=False, timeout=20, headers=HEADERS)
        assert r.status_code == 200

        tree = html.fromstring(r.content)
        links = tree.xpath("//a/@href")
        pdfs = list(dict.fromkeys(
            l for l in links
            if re.match(r'/dyn/\d+/comptes-rendus/seance/session-', l)
            and l.endswith('.pdf')
        ))

        for pdf in pdfs[:3]:
            full_url = BASE + pdf
            r2 = requests.get(full_url, verify=False, timeout=30, headers=HEADERS)
            assert r2.status_code == 200, f"{full_url} returned {r2.status_code}"
            assert r2.content[:4] == b"%PDF", f"{full_url} is not a valid PDF"
            print(f"    ✅ Legislature {leg}: {pdf[-60:]}  ({len(r2.content):,} bytes)")


def test_dyn_pagination_exists():
    """Test that the dyn/ index has pagination links (multiple pages)."""
    leg = 15  # Test with XV which has the most sessions
    url = f"{BASE}/dyn/{leg}/comptes-rendus/seance?page=1&limit=20"
    r = requests.get(url, verify=False, timeout=20, headers=HEADERS)
    assert r.status_code == 200

    tree = html.fromstring(r.content)
    links = tree.xpath("//a/@href")
    page_nums = []
    for l in links:
        m = re.search(r'page=(\d+)', l)
        if m:
            page_nums.append(int(m.group(1)))

    assert len(page_nums) > 0, "No pagination links found"
    max_page = max(page_nums)
    assert max_page > 1, f"Only 1 page of results (max page num found: {max_page})"
    print(f"  ✅ Pagination confirmed: {max_page} pages available")


if __name__ == "__main__":
    test_dyn_index_accessible()
    test_dyn_index_contains_pdf_links()
    test_dyn_pdfs_are_valid()
    test_dyn_pagination_exists()
    print("\n✅ All Legislature XV–XVII tests passed.")
