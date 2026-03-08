"""
Generates citation_data.json by querying OpenAlex API for all VIVA institution works.
Uses cursor pagination to fetch works and compute citation statistics by OA status.

Usage:
    python generate_citations.py

Output:
    citation_data.json
"""

import requests
import json
import time
import statistics
from collections import defaultdict
from datetime import datetime, timezone

API_KEY = "v1hPneNb0TejwTZyZgXEaI"
BASE_URL = "https://api.openalex.org"

# All VIVA institution OpenAlex IDs
VIVA_IDS = "|".join([
    # Public Doctoral
    "I162714631", "I11883440", "I81365321", "I53559539",
    "I51556381", "I184840846", "I859038795", "I16285277",
    # Public Four-Year
    "I177308816", "I141448028", "I103087548", "I191484440",
    "I4901143", "I185641255", "I11786554",
    # Public Two-Year
    "I2802629350", "I902853741", "I138747737", "I76440524",
    "I2802296350", "I4210162787", "I7079364", "I2800951401",
    "I2802739109", "I2800645674", "I2799815508", "I2800249764",
    "I920538115", "I102219622", "I2800666634", "I140472050",
    "I2800477232", "I2800823236", "I171343974", "I2802140220",
    "I2800122815", "I127671586", "I113949470", "I2801288253",
    # Private Nonprofit
    "I887931861", "I2799887800", "I99215809", "I307045584",
    "I36194888", "I200450580", "I4387153953", "I201426678",
    "I896114043", "I177855293", "I152372855", "I26422949",
    "I151328261", "I185439253", "I67789559", "I12559833",
    "I53276908", "I1175298", "I182555378", "I153338809",
    "I41833579", "I200033832", "I178897401", "I2125089",
    "I198073862", "I21978226", "I158012942", "I177833724",
    "I14303183", "I184889055",
])

CITATION_BINS = [
    ("0", lambda x: x == 0),
    ("1-5", lambda x: 1 <= x <= 5),
    ("6-10", lambda x: 6 <= x <= 10),
    ("11-25", lambda x: 11 <= x <= 25),
    ("26-50", lambda x: 26 <= x <= 50),
    ("51-100", lambda x: 51 <= x <= 100),
    ("100+", lambda x: x > 100),
]


def fetch_all_works(year_start=2020, year_end=2025):
    """Fetch all VIVA works using cursor pagination."""
    works = []
    cursor = "*"
    page = 0

    filter_str = (
        f"authorships.institutions.id:{VIVA_IDS},"
        f"publication_year:{year_start}-{year_end}"
    )

    print(f"Fetching works from {year_start} to {year_end}...")

    while cursor:
        url = (
            f"{BASE_URL}/works?"
            f"filter={filter_str}&"
            f"select=id,cited_by_count,open_access,publication_year&"
            f"per_page=200&"
            f"cursor={cursor}&"
            f"api_key={API_KEY}"
        )

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"  Error on page {page}: {e}")
            print("  Retrying in 5 seconds...")
            time.sleep(5)
            continue

        data = response.json()
        results = data.get("results", [])

        if not results:
            break

        for work in results:
            oa = work.get("open_access", {})
            works.append({
                "cited_by_count": work.get("cited_by_count", 0),
                "oa_status": oa.get("oa_status") or "unknown",
                "publication_year": work.get("publication_year"),
            })

        cursor = data.get("meta", {}).get("next_cursor")
        page += 1

        if page % 25 == 0:
            total_expected = data.get("meta", {}).get("count", "?")
            print(f"  Page {page}: {len(works):,} / {total_expected:,} works fetched...")

        # Respect rate limits
        time.sleep(0.05)

    print(f"  Total works fetched: {len(works):,}")
    return works


def compute_statistics(works):
    """Compute citation statistics by OA status and by year."""

    # Group by OA status
    by_status = defaultdict(list)
    for w in works:
        by_status[w["oa_status"]].append(w["cited_by_count"])

    status_stats = {}
    for status, citations in by_status.items():
        if status == "unknown":
            continue

        sorted_c = sorted(citations)
        n = len(sorted_c)

        if n == 0:
            continue

        distribution = []
        for bin_name, bin_fn in CITATION_BINS:
            count = sum(1 for c in citations if bin_fn(c))
            distribution.append({"bin": bin_name, "count": count})

        status_stats[status] = {
            "count": n,
            "mean_citations": round(statistics.mean(citations), 2),
            "median_citations": round(statistics.median(citations), 1),
            "percentile_25": sorted_c[int(n * 0.25)],
            "percentile_75": sorted_c[int(n * 0.75)],
            "percentile_90": sorted_c[int(n * 0.90)],
            "max_citations": max(citations),
            "distribution": distribution,
        }

    # Group by year and status
    by_year = defaultdict(lambda: defaultdict(list))
    for w in works:
        if w["oa_status"] != "unknown":
            by_year[str(w["publication_year"])][w["oa_status"]].append(w["cited_by_count"])

    year_stats = {}
    for year, statuses in sorted(by_year.items()):
        year_stats[year] = {}
        for status, citations in statuses.items():
            if len(citations) > 0:
                year_stats[year][status] = {
                    "count": len(citations),
                    "mean_citations": round(statistics.mean(citations), 2),
                    "median_citations": round(statistics.median(citations), 1),
                }

    return status_stats, year_stats


def main():
    print("=" * 60)
    print("VIVA Citation Data Generator")
    print("=" * 60)

    works = fetch_all_works(2020, 2025)

    if not works:
        print("No works fetched. Check your API key and network connection.")
        return

    print("\nComputing statistics...")
    status_stats, year_stats = compute_statistics(works)

    # Compute overall counts
    oa_types = ["gold", "green", "hybrid", "bronze", "diamond"]
    oa_count = sum(status_stats.get(s, {}).get("count", 0) for s in oa_types)
    closed_count = status_stats.get("closed", {}).get("count", 0)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "institutions": "All VIVA (69 institutions)",
            "years": "2020-2025",
        },
        "summary": {
            "total_works": len([w for w in works if w["oa_status"] != "unknown"]),
            "oa_works": oa_count,
            "closed_works": closed_count,
        },
        "by_oa_status": status_stats,
        "by_year": year_stats,
    }

    with open("citation_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults written to citation_data.json")
    print(f"  Total works: {len(works):,}")
    print(f"  OA works: {oa_count:,}")
    print(f"  Closed works: {closed_count:,}")

    for status in ["gold", "green", "hybrid", "bronze", "diamond", "closed"]:
        if status in status_stats:
            s = status_stats[status]
            print(f"  {status:>8}: {s['count']:>8,} works, mean={s['mean_citations']:.1f}, median={s['median_citations']:.0f}")

    print("\nDone!")


if __name__ == "__main__":
    main()
