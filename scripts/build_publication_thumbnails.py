#!/usr/bin/env python3
"""Build paper-specific thumbnails from openly accessible, primary sources.

The script reads the published bibliography, resolves author manuscripts and
publisher/project assets, extracts Figure 1 when a PDF is available, and writes
small WebP thumbnails plus a machine-readable provenance file.
"""

from __future__ import annotations

import base64
import argparse
import difflib
import html
import json
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pdfplumber
from PIL import Image, ImageFile, ImageOps


ROOT = Path(__file__).resolve().parents[1]
PUBLICATION_HTML = ROOT / "publication" / "index.html"
OUTPUT_DIR = ROOT / "assets" / "img" / "publications"
PDFTOPPM = Path(
    "/Users/lixiangqinqin/.cache/codex-runtimes/"
    "codex-primary-runtime/dependencies/bin/override/pdftoppm"
)
USER_AGENT = "MI2-Lab-Website/1.0 (publication thumbnail builder)"
MAX_DOWNLOAD = 40 * 1024 * 1024
THUMB_SIZE = (440, 280)

ImageFile.LOAD_TRUNCATED_IMAGES = True


# Author-owned project pages are preferred when they include the paper's own
# overview/result figure. The numeric keys match the visible publication order.
PROJECT_REPOS = {
    3: "jiongzhang-john/FiHam",
    10: "jiongzhang-john/3D-Microvascular-Reconstruction",
    12: "jiongzhang-john/CLIP-DSA",
    15: "jiongzhang-john/DSCA",
    16: "jiongzhang-john/Foundation-Models-in-Medical-Imaging",
    17: "jiongzhang-john/OCTA-Stitching-Dataset",
    19: "jiongzhang-john/CNVSeg-Dataset",
    21: "jiongzhang-john/RSAPower",
    27: "Qinkaiyu/CLIP-DR",
}


# Verified author preprints. This also covers records whose website link is the
# final publisher page rather than the arXiv record.
ARXIV_OVERRIDES = {
    2: "2606.28520",
    4: "2604.10737",
    9: "2411.05825",
    11: "2404.01671",
    15: "2406.00341",
    19: "2508.03197",
    20: "2507.01055",
    27: "2407.04068",
    31: "2406.19485",
    38: "2311.06009",
    49: "2208.10745",
    50: "2208.10745",
    51: "2207.11882",
    55: "2102.13588",
    62: "2007.05201",
    70: "2003.03710",
    73: "1809.07987",
    76: "1707.06865",
    80: "1610.06368",
}


# Real author/publisher material for records whose standard resolver is not a
# downloadable paper page.
SOURCE_OVERRIDES = {
    5: [
        "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/daba/12927330/7bd6a34afabd/bmjophth-11-1-g001.jpg",
    ],
    8: [
        "https://research.edgehill.ac.uk/ws/files/101278233/Super-Resolution_Reconstruction_of_OCTA_via_Multi-field-of-view_Representation_Learning.pdf",
    ],
    26: [
        "https://research.edgehill.ac.uk/ws/files/95181617/BIBM2024_ZYD_CAMERAREADY.pdf",
    ],
    43: ["https://resourcecenter.ieee.org/conferences/isbi-2023/spsisbi23vid0278"],
    64: ["https://pmc.ncbi.nlm.nih.gov/articles/PMC7737654/"],
    65: [
        "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/27ba/7174137/f6753c3069ea/nihms-1055657-f0001.jpg",
    ],
    66: ["https://pmc.ncbi.nlm.nih.gov/articles/PMC6928449/"],
    67: [
        "https://dspace.lib.cranfield.ac.uk/server/api/core/bitstreams/027bae51-c421-4138-8e16-89c53aec44de/content",
    ],
    68: [
        "https://mdpi-res.com/d_attachment/applsci/applsci-10-04788/article_deploy/html/images/applsci-10-04788-g001.png",
    ],
    # The correction concerns record 67 and contains no new scientific figure,
    # so it intentionally uses Figure 1 from the corrected article.
    69: [
        "https://dspace.lib.cranfield.ac.uk/server/api/core/bitstreams/027bae51-c421-4138-8e16-89c53aec44de/content",
    ],
    72: [
        "https://pure.tue.nl/ws/portalfiles/portal/139040343/A_fully_automated_pipeline_of_extracting_biomarkers_to_quantify_vascular_changes_in_retina_related_diseases.pdf",
    ],
    74: ["https://pure.tue.nl/ws/files/93318428/boe_9_2_410.pdf"],
    75: [
        "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/97ad/6880863/4c8dde2aa726/nihms-1054931-f0001.jpg",
    ],
    83: ["https://pure.tue.nl/ws/files/45862136/07530915.pdf"],
}


def request(url: str, *, timeout: int = 35, limit: int = MAX_DOWNLOAD) -> tuple[bytes, str, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,image/avif,image/webp,image/png,image/jpeg,text/html;q=0.9,*/*;q=0.7",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError(f"download exceeds {limit} bytes")
        return data, response.url, content_type


def request_json(url: str, *, data: dict | None = None) -> object:
    payload = json.dumps(data).encode() if data is not None else None
    headers = {"User-Agent": USER_AGENT}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def clean_text(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", value)).split())


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def parse_publications() -> list[dict]:
    source = PUBLICATION_HTML.read_text(encoding="utf-8")
    records = []
    for index, block in enumerate(
        re.findall(r'<article class="publication-item">(.*?)</article>', source, re.S), 1
    ):
        title_match = re.search(r"<h3>(.*?)</h3>", block, re.S)
        if not title_match:
            continue
        title = clean_text(title_match.group(1))
        links = re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', block)
        paper_url = next((url for url, label in links if label.strip() == "Paper"), "")
        support_urls = [url for url, label in links if label.strip() != "Paper"]
        doi = ""
        if "doi.org/" in paper_url:
            doi = urllib.parse.unquote(paper_url.split("doi.org/", 1)[1])
        records.append(
            {
                "index": index,
                "title": title,
                "paper_url": paper_url,
                "support_urls": support_urls,
                "doi": doi,
            }
        )
    return records


def semantic_scholar_metadata(records: list[dict]) -> dict[str, dict]:
    ids = [f"DOI:{record['doi']}" for record in records if record["doi"]]
    if not ids:
        return {}
    endpoint = (
        "https://api.semanticscholar.org/graph/v1/paper/batch"
        "?fields=title,openAccessPdf,externalIds"
    )
    for attempt in range(3):
        try:
            result = request_json(endpoint, data={"ids": ids})
            return {
                item.get("externalIds", {}).get("DOI", "").lower(): item
                for item in result
                if item
            }
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 2:
                print(f"Semantic Scholar metadata unavailable: {exc}")
                return {}
            time.sleep(12 * (attempt + 1))
        except Exception as exc:  # Network metadata is helpful, not mandatory.
            print(f"Semantic Scholar metadata unavailable: {exc}")
            return {}
    return {}


def arxiv_author_records() -> list[tuple[str, str]]:
    query = urllib.parse.urlencode(
        {
            "search_query": 'au:"Jiong Zhang"',
            "start": 0,
            "max_results": 200,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    try:
        data, _, _ = request(f"https://export.arxiv.org/api/query?{query}")
        root = ET.fromstring(data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        output = []
        for entry in root.findall("atom:entry", ns):
            title_node = entry.find("atom:title", ns)
            id_node = entry.find("atom:id", ns)
            if title_node is None or id_node is None:
                continue
            arxiv_id = id_node.text.rsplit("/", 1)[-1].split("v", 1)[0]
            output.append((clean_text(title_node.text), arxiv_id))
        return output
    except Exception as exc:
        print(f"arXiv metadata unavailable: {exc}")
        return []


def inferred_arxiv(record: dict, author_records: list[tuple[str, str]], s2: dict) -> str:
    index = record["index"]
    if index in ARXIV_OVERRIDES:
        return ARXIV_OVERRIDES[index]
    external = s2.get("externalIds", {}) if s2 else {}
    if external.get("ArXiv"):
        return external["ArXiv"]
    if not author_records:
        return ""
    wanted = normalize_title(record["title"])
    best_title, best_id = max(
        author_records,
        key=lambda item: difflib.SequenceMatcher(None, wanted, normalize_title(item[0])).ratio(),
    )
    score = difflib.SequenceMatcher(None, wanted, normalize_title(best_title)).ratio()
    return best_id if score >= 0.88 else ""


def github_project_image(repo: str) -> tuple[bytes, str] | None:
    try:
        details = request_json(f"https://api.github.com/repos/{repo}")
        branch = details.get("default_branch", "main")
        tree = request_json(
            f"https://api.github.com/repos/{repo}/git/trees/{urllib.parse.quote(branch)}?recursive=1"
        )
    except Exception as exc:
        print(f"  GitHub project lookup failed for {repo}: {exc}")
        return None

    candidates = []
    for item in tree.get("tree", []):
        path = item.get("path", "")
        if item.get("type") != "blob" or not re.search(r"\.(png|jpe?g|webp)$", path, re.I):
            continue
        lowered = path.lower()
        if any(word in lowered for word in ("logo", "badge", "icon", "avatar")):
            continue
        score = 0
        for rank, word in enumerate(
            ("overview", "framework", "pipeline", "method", "figure", "result", "demo", "sample", "visual"),
            1,
        ):
            if word in lowered:
                score += 20 - rank
        score += min(item.get("size", 0) // 20_000, 12)
        candidates.append((score, item))

    for _, item in sorted(candidates, key=lambda value: value[0], reverse=True):
        if item.get("size", 0) > 12 * 1024 * 1024:
            continue
        try:
            blob = request_json(item["url"])
            if blob.get("encoding") != "base64":
                continue
            data = base64.b64decode(blob["content"])
            if image_is_usable(data):
                return data, f"https://github.com/{repo}/blob/{branch}/{item['path']}"
        except Exception:
            continue
    return None


def image_is_usable(data: bytes) -> bool:
    try:
        import io

        with Image.open(io.BytesIO(data)) as image:
            return image.width >= 240 and image.height >= 140
    except Exception:
        return False


def save_thumbnail(data: bytes, output_path: Path) -> None:
    import io

    with Image.open(io.BytesIO(data)) as source:
        source = ImageOps.exif_transpose(source).convert("RGB")
        if source.width / max(source.height, 1) > 2.7:
            source = ImageOps.fit(source, (source.width, int(source.width / 2.1)), method=Image.Resampling.LANCZOS)
        thumb = ImageOps.pad(
            source,
            THUMB_SIZE,
            method=Image.Resampling.LANCZOS,
            color="#eef3f7",
            centering=(0.5, 0.5),
        )
        thumb.save(output_path, "WEBP", quality=82, method=6)


def find_figure_page(pdf_path: Path) -> tuple[int, tuple[float, float, float, float] | None]:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_index, page in enumerate(pdf.pages[:9]):
                matches = page.search(r"\bFig(?:ure)?\.?\s*1\b", regex=True, case=False) or []
                for match in matches:
                    # Captions start near the left margin; references to Fig. 1
                    # inside body text should not win over the real caption.
                    if float(match.get("x0", page.width)) > page.width * 0.32:
                        continue
                    caption_top = float(match.get("top", page.height * 0.72))
                    images = []
                    for image in page.images:
                        top = float(image.get("top", 0))
                        bottom = float(image.get("bottom", top))
                        width = float(image.get("x1", 0)) - float(image.get("x0", 0))
                        height = bottom - top
                        if bottom <= caption_top + 8 and width * height >= page.width * page.height * 0.012:
                            images.append(image)
                    if images:
                        x0 = max(0, min(float(image.get("x0", 0)) for image in images) - 14)
                        x1 = min(page.width, max(float(image.get("x1", page.width)) for image in images) + 14)
                        top = max(0, min(float(image.get("top", 0)) for image in images) - 14)
                        bottom = min(caption_top - 3, max(float(image.get("bottom", caption_top)) for image in images) + 14)
                    else:
                        x0, x1 = page.width * 0.04, page.width * 0.96
                        top = max(page.height * 0.04, caption_top - page.height * 0.56)
                        bottom = max(top + page.height * 0.16, caption_top - 4)
                    return page_index + 1, (x0, top, x1, bottom)
    except Exception as exc:
        print(f"  Figure detection failed: {exc}")
    return 1, None


def thumbnail_from_pdf(data: bytes, output_path: Path) -> bool:
    with tempfile.TemporaryDirectory(prefix="mi2-paper-") as temp_dir:
        temp = Path(temp_dir)
        pdf_path = temp / "paper.pdf"
        pdf_path.write_bytes(data)
        page_number, crop = find_figure_page(pdf_path)
        output_root = temp / "page"
        command = [
            str(PDFTOPPM),
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            "-r",
            "144",
            "-png",
            "-singlefile",
            str(pdf_path),
            str(output_root),
        ]
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=55)
            rendered = output_root.with_suffix(".png")
            with Image.open(rendered) as page_image:
                page_image = page_image.convert("RGB")
                if crop:
                    with pdfplumber.open(pdf_path) as pdf:
                        page = pdf.pages[page_number - 1]
                        scale_x = page_image.width / page.width
                        scale_y = page_image.height / page.height
                    box = (
                        int(crop[0] * scale_x),
                        int(crop[1] * scale_y),
                        int(crop[2] * scale_x),
                        int(crop[3] * scale_y),
                    )
                    page_image = page_image.crop(box)
                else:
                    page_image = page_image.crop(
                        (int(page_image.width * 0.08), 0, int(page_image.width * 0.92), int(page_image.height * 0.84))
                    )
                thumb = ImageOps.pad(
                    page_image,
                    THUMB_SIZE,
                    method=Image.Resampling.LANCZOS,
                    color="#eef3f7",
                    centering=(0.5, 0.42),
                )
                thumb.save(output_path, "WEBP", quality=82, method=6)
            return True
        except Exception as exc:
            print(f"  PDF render failed: {exc}")
            return False


def absolute_url(base: str, value: str) -> str:
    return urllib.parse.urljoin(base, html.unescape(value).replace("&amp;", "&"))


def html_candidates(page: bytes, base_url: str) -> tuple[list[str], list[str]]:
    text = page.decode("utf-8", "ignore")
    pdf_urls = []
    image_urls = []

    for pattern in (
        r'<meta[^>]+(?:name|property)=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\']citation_pdf_url["\']',
        r'<a[^>]+href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']',
    ):
        pdf_urls.extend(absolute_url(base_url, url) for url in re.findall(pattern, text, re.I))

    figure_blocks = re.findall(r"<figure\b.*?</figure>", text, re.I | re.S)
    for block in figure_blocks:
        image_urls.extend(
            absolute_url(base_url, url)
            for url in re.findall(r'<img[^>]+(?:src|data-src)=["\']([^"\']+)', block, re.I)
        )
    image_urls.extend(
        absolute_url(base_url, url)
        for url in re.findall(
            r'<img[^>]+(?:src|data-src)=["\']([^"\']*(?:fig|mediaobject|article|graphic)[^"\']*)',
            text,
            re.I,
        )
    )
    for pattern in (
        r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']',
    ):
        image_urls.extend(absolute_url(base_url, url) for url in re.findall(pattern, text, re.I))

    image_urls = [
        url
        for url in image_urls
        if not any(word in url.lower() for word in ("logo", "headerimage", "icon", "avatar", "brandmark"))
    ]
    return list(dict.fromkeys(pdf_urls)), list(dict.fromkeys(image_urls))


def resolve_source(url: str, output_path: Path, visited: set[str], depth: int = 0) -> tuple[bool, str, str]:
    if not url or url in visited or depth > 2:
        return False, "", ""
    visited.add(url)
    try:
        data, final_url, content_type = request(url)
    except Exception as exc:
        return False, "", f"{type(exc).__name__}: {exc}"

    if data.startswith(b"%PDF") or content_type == "application/pdf":
        if thumbnail_from_pdf(data, output_path):
            return True, final_url, "paper figure"
        return False, "", "PDF render failed"
    if content_type.startswith("image/") or image_is_usable(data):
        try:
            save_thumbnail(data, output_path)
            return True, final_url, "paper/project image"
        except Exception as exc:
            return False, "", f"image processing failed: {exc}"
    if "html" not in content_type and b"<html" not in data[:2000].lower():
        return False, "", f"unsupported content type {content_type}"

    pdf_urls, image_urls = html_candidates(data, final_url)
    for candidate in image_urls[:10]:
        success, used_url, source_type = resolve_source(candidate, output_path, visited, depth + 1)
        if success:
            return success, used_url, source_type
    for candidate in pdf_urls[:8]:
        success, used_url, source_type = resolve_source(candidate, output_path, visited, depth + 1)
        if success:
            return success, used_url, source_type
    return False, "", "no usable figure or PDF found on page"


def elsevier_candidates(record: dict) -> list[str]:
    if not record["doi"].lower().startswith("10.1016/") and "sciencedirect.com" not in record["paper_url"]:
        return []
    pii_match = re.search(r"/pii/([A-Z0-9]+)", record["paper_url"], re.I)
    if not pii_match and record["doi"]:
        try:
            _, final_url, _ = request(f"https://doi.org/{record['doi']}", limit=2_000_000)
            pii_match = re.search(r"/pii/([A-Z0-9]+)", final_url, re.I)
        except Exception:
            pass
    if not pii_match:
        return []
    pii = pii_match.group(1)
    return [
        f"https://ars.els-cdn.com/content/image/1-s2.0-{pii}-gr1.jpg",
        f"https://ars.els-cdn.com/content/image/1-s2.0-{pii}-fig1.jpg",
    ]


def candidate_urls(record: dict, arxiv_id: str, s2: dict) -> list[str]:
    urls = []
    urls.extend(SOURCE_OVERRIDES.get(record["index"], []))
    urls.extend(elsevier_candidates(record))
    if arxiv_id:
        urls.append(f"https://arxiv.org/pdf/{arxiv_id}")
    doi = record["doi"]
    if doi.lower().startswith("10.1007/"):
        urls.append(f"https://link.springer.com/content/pdf/{doi}.pdf")
    open_pdf = (s2.get("openAccessPdf") or {}).get("url", "") if s2 else ""
    if open_pdf:
        urls.append(open_pdf)
    urls.append(record["paper_url"])
    urls.extend(record["support_urls"])
    return list(dict.fromkeys(url for url in urls if url))


def parse_only(value: str) -> set[int]:
    selected = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = (int(item) for item in part.split("-", 1))
            selected.update(range(start, end + 1))
        else:
            selected.add(int(part))
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="", help="comma-separated publication numbers or ranges")
    parser.add_argument(
        "--reuse-source",
        action="store_true",
        help="regenerate selected thumbnails from the provenance file without re-resolving metadata",
    )
    args = parser.parse_args()
    records = parse_publications()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    selected = parse_only(args.only) if args.only else {record["index"] for record in records}
    work_records = [record for record in records if record["index"] in selected]
    source_path = OUTPUT_DIR / "sources.json"
    if source_path.exists():
        existing = {entry["id"]: entry for entry in json.loads(source_path.read_text(encoding="utf-8"))}
    else:
        existing = {}

    if args.reuse_source:
        def refresh(record: dict) -> tuple[dict, bool, str]:
            entry = existing.get(f"pub-{record['index']:03d}", {})
            source_url = entry.get("image_source", "")
            if not source_url:
                return record, False, "no recorded source"
            candidates = [source_url]
            if "?" in source_url:
                candidates.append(source_url.split("?", 1)[0])
            output_path = OUTPUT_DIR / f"pub-{record['index']:03d}.webp"
            last_error = ""
            for candidate in candidates:
                success, _, result = resolve_source(candidate, output_path, set())
                if success:
                    return record, True, source_url
                last_error = result
            return record, False, last_error

        failures = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            jobs = [executor.submit(refresh, record) for record in work_records]
            for job in as_completed(jobs):
                record, success, detail = job.result()
                if success:
                    print(f"[{record['index']:02d}] ✓ refreshed {detail}")
                else:
                    failures.append(record)
                    print(f"[{record['index']:02d}] ✗ {detail}")
        print(f"\nRefreshed {len(work_records) - len(failures)}/{len(work_records)} requested thumbnails.")
        return 1 if failures else 0

    semantic = semantic_scholar_metadata(work_records)
    arxiv_records = arxiv_author_records()
    sources = dict(existing)
    missing = []

    for record in work_records:
        index = record["index"]
        output_path = OUTPUT_DIR / f"pub-{index:03d}.webp"
        print(f"[{index:02d}/{len(records)}] {record['title']}")
        source_url = ""
        source_type = ""

        repo = PROJECT_REPOS.get(index)
        if repo:
            project_image = github_project_image(repo)
            if project_image:
                data, source_url = project_image
                save_thumbnail(data, output_path)
                source_type = "author project image"

        s2 = semantic.get(record["doi"].lower(), {}) if record["doi"] else {}
        arxiv_id = inferred_arxiv(record, arxiv_records, s2)
        errors = []
        if not source_url:
            for url in candidate_urls(record, arxiv_id, s2):
                success, used_url, result = resolve_source(url, output_path, set())
                if success:
                    source_url = used_url
                    source_type = result
                    break
                errors.append(f"{url}: {result}")

        entry = {
            "id": f"pub-{index:03d}",
            "title": record["title"],
            "paper_url": record["paper_url"],
            "image": f"/assets/img/publications/pub-{index:03d}.webp" if source_url else "",
            "image_source": source_url,
            "source_type": source_type,
        }
        sources[entry["id"]] = entry
        if source_url:
            print(f"  ✓ {source_type}: {source_url}")
        else:
            missing.append(record)
            print("  ✗ no open primary-source image found")
            for error in errors[-2:]:
                print(f"    {error}")

    ordered_sources = [sources[f"pub-{record['index']:03d}"] for record in records if f"pub-{record['index']:03d}" in sources]
    source_path.write_text(
        json.dumps(ordered_sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\nCreated {len(work_records) - len(missing)}/{len(work_records)} requested real-paper thumbnails.")
    if missing:
        print("Missing:")
        for record in missing:
            print(f"  {record['index']:02d} {record['title']}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
