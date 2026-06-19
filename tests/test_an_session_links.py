#!/usr/bin/env python3
"""
test_an_session_links.py

Verifies that session index pages across different AN legislature eras
are accessible and contain expected session links.

Why this test exists:
    Each legislature era has a different URL scheme for session indices.
    This test confirms the index pages are still reachable, which is a
    prerequisite for URL discovery. If the Assemblée nationale changes
    its site structure, this test will fail first, alerting us to update
    the discovery logic.

What this test does:
    - Tests the archives subdomain index for Legislature XI
    - Tests the www subdomain session indices for Legislatures XII–XIV
    - Tests the dyn/ API index for Legislatures XV–XVII
"""

import requests
from lxml import html

requests.packages.urllib3.disable_warnings()

BASE = "https://www.assemblee-nationale.fr"
ARCHIVES = "https://archives.assemblee-nationale.fr"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FrenchParliamentaryCorpus/1.0)"}


def test_archives_index():
    """Test that the Legislature XI archives index page is accessible."""
    url = f"{ARCHIVES}/11/cri/index.html"
    r = requests.get(url, verify=False, timeout=15, headers=HEADERS)
    assert r.status_code == 200, f"Archives index returned {r.status_code}"
    tree = html.fromstring(r.content)
    links = tree.xpath("//a/@href")
    session_links = [l for l in links if "ordinaire" in l or "extraordinaire" in l]
    assert len(session_links) > 0, "No session links found in archives index"
    print(f"Archives index: {len(session_links)} session links found")


def test_archives_session_page():
    """Test that a specific Legislature XI session page is accessible."""
    url = f"{ARCHIVES}/11/cri/11-1997-1998-ordinaire1.html"
    r = requests.get(url, verify=False, timeout=15, headers=HEADERS)
    assert r.status_code == 200, f"Session page returned {r.status_code}"
    tree = html.fromstring(r.content)
    links = tree.xpath("//a/@href")
    print(f"Session page (1997-1998 ordinaire1): {len(links)} links found")


def test_www_session_index_accessible():
    """Test that XII–XIV www session indices are accessible."""
    for leg in [12, 13, 14]:
        sessions = {
            12: "2002-2003",
            13: "2007-2008",
            14: "2012-2013",
        }
        url = f"{BASE}/{leg}/cri/{sessions[leg]}/"
        r = requests.get(url, verify=False, timeout=15, headers=HEADERS)
        assert r.status_code == 200, f"Session index legislature {leg} returned {r.status_code}"
        print(f"  Legislature {leg} session index: {r.status_code}")


def test_dyn_index_works():
    """Test that the dyn/ index works for all modern legislatures."""
    for leg in [15, 16, 17]:
        url = f"{BASE}/dyn/{leg}/comptes-rendus/seance?page=1&limit=20"
        r = requests.get(url, verify=False, timeout=20, headers=HEADERS)
        assert r.status_code == 200, f"dyn/ index leg {leg} returned {r.status_code}"
        print(f"  Legislature {leg} dyn/ index: {r.status_code}")


if __name__ == "__main__":
    test_archives_index()
    test_archives_session_page()
    test_www_session_index_accessible()
    test_dyn_index_works()
    print("\n✅ All session link tests passed.")
