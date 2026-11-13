
import re
import requests
import fitz

from pathlib import Path
from difflib import SequenceMatcher
from urllib.parse import quote
from sentence_transformers import SentenceTransformer, util


# ==========================================
# STEP 1: PROJECT PATHS AND MODEL
# ==========================================

PROJECT_FOLDER = Path("/content/drive/MyDrive/ClaimCraft-AI")
PAPER_FOLDER = PROJECT_FOLDER / "uploads" / "Research_Papers"
PAPER_FOLDER.mkdir(parents=True, exist_ok=True)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

MIN_SIMILARITY = 0.25

_model = None


def get_model():
    global _model

    if _model is None:
        print("Loading MiniLM model...")
        _model = SentenceTransformer(MODEL_NAME)
        print("MiniLM loaded successfully!")

    return _model


# ==========================================
# STEP 2: DOI CLEANING
# ==========================================

def normalize_doi(doi):
    if not doi:
        return None

    doi = str(doi).strip()

    doi = re.sub(
        r"^https?://(dx\.)?doi\.org/",
        "",
        doi,
        flags=re.IGNORECASE
    )

    return doi.strip().rstrip(" .")


# ==========================================
# STEP 3: SEARCH RESEARCH PAPER ON OPENALEX
# ==========================================

def search_research_paper(reference):
    doi = normalize_doi(reference.get("doi"))
    title = reference.get("title")
    year = reference.get("year")

    # First preference: DOI search
    if doi:
        print("Searching paper using DOI:", doi)

        url = (
            "https://api.openalex.org/works/https://doi.org/"
            + quote(doi, safe="/")
        )

        try:
            response = requests.get(url, timeout=30)

            if response.status_code == 200:
                return response.json()

        except requests.RequestException as error:
            print("DOI search error:", error)

    # Second preference: title search
    if not title:
        return None

    print("Searching paper using title:", title)

    try:
        response = requests.get(
            "https://api.openalex.org/works",
            params={
                "search": title,
                "per_page": 10
            },
            timeout=30
        )

        response.raise_for_status()

        results = response.json().get("results", [])
        normalized_title = title.lower().strip()

        for work in results:
            result_title = (
                work.get("title") or ""
            ).lower().strip()

            title_score = SequenceMatcher(
                None,
                normalized_title,
                result_title
            ).ratio()

            result_year = str(
                work.get("publication_year", "")
            )

            year_matches = (
                not year or str(year) == result_year
            )

            if title_score >= 0.85 and year_matches:
                return work

    except requests.RequestException as error:
        print("Title search error:", error)

    return None


# ==========================================
# STEP 4: FIND PDF THROUGH OPENALEX
# ==========================================

def find_pdf_url(work):
    best_location = work.get("best_oa_location") or {}

    if best_location.get("pdf_url"):
        return best_location["pdf_url"]

    locations = work.get("locations") or []

    for location in locations:
        if location.get("pdf_url"):
            return location["pdf_url"]

    return None


# ==========================================
# STEP 5: SEMANTIC SCHOLAR PDF FALLBACK
# ==========================================

def find_semantic_scholar_pdf(reference):
    doi = normalize_doi(reference.get("doi"))

    if not doi:
        return None

    print("Checking Semantic Scholar for an open-access PDF...")

    url = (
        "https://api.semanticscholar.org/graph/v1/paper/DOI:"
        + quote(doi, safe="")
    )

    try:
        response = requests.get(
            url,
            params={
                "fields": "title,openAccessPdf,year"
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()

            pdf_info = data.get("openAccessPdf") or {}
            pdf_url = pdf_info.get("url")

            if pdf_url:
                print("Open-access PDF found through Semantic Scholar.")
                return pdf_url

    except requests.RequestException as error:
        print("Semantic Scholar search error:", error)

    return None


# ==========================================
# STEP 6: DOWNLOAD RESEARCH PAPER PDF
# ==========================================

def download_research_paper(work, pdf_url):
    doi = (
        work.get("doi")
        or work.get("id")
        or "research_paper"
    )

    safe_name = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        doi
    ).strip("_")

    pdf_path = PAPER_FOLDER / f"{safe_name}.pdf"

    if pdf_path.exists() and pdf_path.stat().st_size > 1000:
        print("Paper already downloaded:", pdf_path)
        return pdf_path

    print("Downloading research paper...")

    try:
        response = requests.get(
            pdf_url,
            timeout=60,
            headers={
                "User-Agent": "ClaimCraftAI/1.0"
            }
        )

        response.raise_for_status()

        if b"%PDF-" not in response.content[:1024]:
            print("The link did not return a valid PDF.")
            return None

        pdf_path.write_bytes(response.content)

        print("Paper downloaded successfully.")
        return pdf_path

    except requests.RequestException as error:
        print("PDF download error:", error)
        return None


# ==========================================
# STEP 7: IDENTIFY REFERENCES SECTION
# ==========================================

def is_reference_heading(line):
    cleaned = line.strip().lower()

    cleaned = re.sub(
        r"^\d+(\.\d+)*\.?\s*",
        "",
        cleaned
    )

    return cleaned in {
        "references",
        "reference",
        "bibliography",
        "works cited",
        "literature cited",
        "references and notes"
    }


# ==========================================
# STEP 8: REMOVE NON-EVIDENCE CONTENT
# ==========================================

def is_metadata_line(line):
    line = line.strip()

    if not line:
        return True

    # DOI information
    if re.search(
        r"\bdoi\s*:\s*|doi\.org/",
        line,
        re.IGNORECASE
    ):
        return True

    # Lines containing only URLs
    if re.fullmatch(
        r"https?://\S+",
        line,
        re.IGNORECASE
    ):
        return True

    # Publication metadata
    metadata_patterns = [
        r"^\s*(received|accepted|published online|published)\s*:",
        r"^\s*copyright\s",
        r"^\s*all rights reserved",
        r"^\s*issn\s*[:\-]",
        r"^\s*volume\s+\d+.*issue\s+\d+"
    ]

    for pattern in metadata_patterns:
        if re.search(
            pattern,
            line,
            re.IGNORECASE
        ):
            return True

    return False


def identify_section_heading(line):
    """
    Detect common academic section headings.
    Used as a ranking hint, not as proof of support.
    """

    cleaned = re.sub(
        r"^\s*\d+(\.\d+)*\.?\s*",
        "",
        line.strip().lower()
    )

    cleaned = re.sub(
        r"[^a-z ]",
        "",
        cleaned
    ).strip()

    section_names = {
        "abstract": "Abstract",
        "introduction": "Introduction",
        "background": "Background",
        "related work": "Related Work",
        "literature review": "Literature Review",
        "method": "Methods",
        "methods": "Methods",
        "methodology": "Methods",
        "results": "Results",
        "findings": "Results",
        "results and findings": "Results",
        "discussion": "Discussion",
        "results and discussion": "Results/Discussion",
        "conclusion": "Conclusion",
        "conclusions": "Conclusion",
        "limitations": "Limitations"
    }

    return section_names.get(cleaned)


# ==========================================
# STEP 9: EXTRACT ACTUAL RESEARCH TEXT
# ==========================================

def clean_research_pages(pages):
    cleaned_pages = []
    inside_references = False

    for page in pages:
        page_number = page["page"]
        cleaned_lines = []

        for line in page["text"].splitlines():
            line = line.strip()

            if not line:
                continue

            # Stop extracting when References section starts
            if is_reference_heading(line):
                inside_references = True

                print(
                    "References section detected on page:",
                    page_number
                )

                break

            if inside_references:
                continue

            if is_metadata_line(line):
                continue

            cleaned_lines.append(line)

        if cleaned_lines:
            cleaned_pages.append({
                "page": page_number,
                "text": "\n".join(cleaned_lines)
            })

    print(
        "Pages remaining after cleaning:",
        len(cleaned_pages)
    )

    return cleaned_pages


# ==========================================
# STEP 10: EXTRACT PDF TEXT WITH PAGE NUMBERS
# ==========================================

def extract_paper_pages(pdf_path):
    print("Extracting research paper text...")

    pages = []

    pdf_document = fitz.open(pdf_path)

    try:
        for page_number, page in enumerate(
            pdf_document,
            start=1
        ):
            page_text = page.get_text("text")

            if page_text.strip():
                pages.append({
                    "page": page_number,
                    "text": page_text
                })

    finally:
        pdf_document.close()

    print("Paper pages extracted:", len(pages))

    return clean_research_pages(pages)


# ==========================================
# STEP 11: SPLIT CLAIM INTO SEARCH QUERIES
# ==========================================

def build_claim_queries(claim):
    """
    Keep the complete claim as the main query.
    Also create smaller queries for separate clauses
    in compound claims.
    """

    claim = re.sub(
        r"\s+",
        " ",
        str(claim)
    ).strip()

    queries = [claim]

    parts = re.split(
        r"\s+(?:and|while|whereas|but|although|as well as)\s+",
        claim,
        flags=re.IGNORECASE
    )

    for part in parts:
        part = part.strip(" ,;:.")

        if (
            len(part.split()) >= 5
            and part.lower() not in {
                item.lower() for item in queries
            }
        ):
            queries.append(part)

    return queries[:4]


# ==========================================
# STEP 12: CREATE CONTEXTUAL EVIDENCE PASSAGES
# ==========================================

def create_passages(pages):
    """
    Create overlapping passages of up to 4 sentences.
    Preserve the original PDF page and detected section.
    """

    passages = []

    for page in pages:
        current_section = "Unknown"
        sentence_records = []

        for line in page["text"].splitlines():
            line = line.strip()

            if not line:
                continue

            detected_section = identify_section_heading(line)

            if detected_section:
                current_section = detected_section
                continue

            if is_metadata_line(line):
                continue

            sentences = re.split(
                r"(?<=[.!?])\s+",
                line
            )

            for sentence in sentences:
                sentence = sentence.strip()
                words = sentence.split()

                if len(words) < 5:
                    continue

                if is_metadata_line(sentence):
                    continue

                # Remove obvious bibliographic fragments
                if re.search(
                    r"\b(retrieved from|available at|copyright\s+\d{4})\b",
                    sentence,
                    re.IGNORECASE
                ):
                    continue

                sentence_records.append({
                    "text": sentence,
                    "section": current_section
                })

        # Four-sentence windows with overlap
        window_size = 4
        step_size = 2

        for start in range(
            0,
            len(sentence_records),
            step_size
        ):
            window = sentence_records[
                start:start + window_size
            ]

            if not window:
                continue

            passage_text = " ".join(
                item["text"] for item in window
            )

            if len(passage_text.split()) < 20:
                continue

            # Find the most frequent section label
            section_counts = {}

            for item in window:
                section_counts[item["section"]] = (
                    section_counts.get(item["section"], 0) + 1
                )

            section = max(
                section_counts,
                key=section_counts.get
            )

            passages.append({
                "text": passage_text,
                "page": page["page"],
                "section": section
            })

    print(
        "Contextual evidence passages created:",
        len(passages)
    )

    return passages


# ==========================================
# STEP 13: RANK EVIDENCE FOR THE CLAIM
# ==========================================

def section_priority(section):
    """
    Results and Discussion often contain findings.
    This is only a small ranking preference.
    """

    priorities = {
        "Results": 0.035,
        "Results/Discussion": 0.035,
        "Discussion": 0.030,
        "Conclusion": 0.020,
        "Abstract": 0.005
    }

    return priorities.get(section, 0.0)


def retrieve_relevant_evidence(
    claim,
    passages,
    top_k=3
):
    if not passages:
        return []

    model = get_model()

    queries = build_claim_queries(claim)

    passage_texts = [
        passage["text"]
        for passage in passages
    ]

    print("Claim search queries created:", len(queries))
    print("Creating passage embeddings...")

    query_embeddings = model.encode(
        queries,
        convert_to_tensor=True,
        normalize_embeddings=True
    )

    passage_embeddings = model.encode(
        passage_texts,
        convert_to_tensor=True,
        normalize_embeddings=True
    )

    similarity_matrix = util.cos_sim(
        query_embeddings,
        passage_embeddings
    )

    ranked = []

    for passage_index, passage in enumerate(passages):

        scores = [
            float(
                similarity_matrix[query_index][passage_index]
            )
            for query_index in range(len(queries))
        ]

        best_similarity = max(scores)

        # Count how many separate claim parts match
        matched_parts = sum(
            score >= 0.35
            for score in scores
        )

        coverage_bonus = 0.015 * matched_parts

        section_bonus = section_priority(
            passage.get("section", "Unknown")
        )

        final_score = (
            best_similarity
            + coverage_bonus
            + section_bonus
        )

        if best_similarity >= MIN_SIMILARITY:
            ranked.append({
                "passage": passage,
                "similarity": best_similarity,
                "ranking_score": final_score,
                "matched_parts": matched_parts
            })

    ranked.sort(
        key=lambda item: item["ranking_score"],
        reverse=True
    )

    # Select top results while avoiding duplicate passages
    selected = []
    seen_texts = set()

    for item in ranked:
        passage = item["passage"]

        normalized_text = re.sub(
            r"\W+",
            " ",
            passage["text"].lower()
        ).strip()

        if normalized_text in seen_texts:
            continue

        seen_texts.add(normalized_text)

        selected.append({
            "evidence": passage["text"],
            "page": passage["page"],
            "similarity_score": round(
                item["similarity"],
                4
            ),
            "section": passage.get(
                "section",
                "Unknown"
            ),
            "matched_claim_parts": item["matched_parts"]
        })

        if len(selected) >= top_k:
            break

    print(
        "Relevant evidence passages selected:",
        len(selected)
    )

    for number, item in enumerate(
        selected,
        start=1
    ):
        print(
            f"Evidence {number}: "
            f"page={item['page']}, "
            f"section={item['section']}, "
            f"similarity={item['similarity_score']}"
        )

    return selected


# ==========================================
# STEP 14: COMPLETE EVIDENCE RETRIEVAL
# ==========================================

def retrieve_evidence(claim, reference, top_k=3):

    print("\n========== RESEARCH PAPER SEARCH ==========")

    work = search_research_paper(reference)

    if not work:
        return {
            "status": "paper_not_found",
            "message": "Research paper could not be identified."
        }

    print("Paper found:", work.get("title"))

    # First try OpenAlex
    pdf_url = find_pdf_url(work)

    # If OpenAlex has no PDF, try Semantic Scholar
    if not pdf_url:
        pdf_url = find_semantic_scholar_pdf(reference)

    if not pdf_url:
        return {
            "status": "full_text_unavailable",
            "message": (
                "Paper was identified, but no accessible "
                "open-access PDF was found."
            ),
            "paper_title": work.get("title"),
            "doi": work.get("doi")
        }

    pdf_path = download_research_paper(
        work,
        pdf_url
    )

    if not pdf_path:
        return {
            "status": "download_failed",
            "message": (
                "Could not download a valid research paper PDF."
            )
        }

    paper_pages = extract_paper_pages(pdf_path)

    if not paper_pages:
        return {
            "status": "no_passages",
            "message": "No readable research text was extracted.",
            "paper_title": work.get("title"),
            "doi": work.get("doi")
        }

    passages = create_passages(paper_pages)

    evidence = retrieve_relevant_evidence(
        claim,
        passages,
        top_k=top_k
    )

    return {
        "status": "success" if evidence else "no_passages",
        "paper_title": work.get("title"),
        "doi": work.get("doi"),
        "paper_url": pdf_url,
        "local_pdf": str(pdf_path),
        "total_pages": len(paper_pages),
        "evidence": evidence
    }


# ==========================================
# STEP 15: OPTIONAL MANUAL TEST
# ==========================================

if __name__ == "__main__":

    test_claim = (
        "In a real primary-school setting, retrieval-practice "
        "activities were associated with improved delayed learning, "
        "and the sequence of activities was relevant to the learning outcomes."
    )

    test_reference = {
        "authors": "Franzoi et al.",
        "year": "2025",
        "title": (
            "Retrieval practice enhances learning in real primary school "
            "settings, whether distributed or not"
        ),
        "doi": "10.3389/fpsyg.2025.1632206"
    }

    result = retrieve_evidence(
        test_claim,
        test_reference,
        top_k=3
    )

    print("\n========== FINAL EVIDENCE RESULTS ==========")

    print("Status:", result["status"])
    print("Paper:", result.get("paper_title"))

    for item in result.get("evidence", []):

        print("\nEvidence:", item["evidence"])
        print("Page:", item["page"])
        print("Section:", item.get("section"))
        print("Similarity:", item["similarity_score"])
        print(
            "Matched claim parts:",
            item.get("matched_claim_parts")
        )
