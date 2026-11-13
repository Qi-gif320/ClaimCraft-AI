
import re


# ==========================================
# STEP 1: EXTRACT CITATIONS FROM CLAIM
# ==========================================

def extract_citations(claim):

    citations = []

    parenthetical_pattern = (
        r'\(([^()]*\b(?:19|20)\d{2}[a-z]?\b[^()]*)\)'
    )

    parenthetical_matches = re.findall(
        parenthetical_pattern,
        claim
    )

    for citation in parenthetical_matches:
        citations.append(citation.strip())

    narrative_pattern = (
        r'\b[A-Z][A-Za-z\'’-]+'
        r'(?:\s+(?:and|&)\s+[A-Z][A-Za-z\'’-]+'
        r'|\s+et\s+al\.)?'
        r'\s*\((?:19|20)\d{2}[a-z]?\)'
    )

    narrative_matches = re.findall(
        narrative_pattern,
        claim
    )

    for citation in narrative_matches:

        if citation not in citations:
            citations.append(citation.strip())

    return citations


# ==========================================
# STEP 2: EXTRACT REFERENCES SECTION
# ==========================================

def extract_reference_section(pages):

    reference_lines = []
    reference_started = False

    headings = [
        "references",
        "reference",
        "bibliography",
        "works cited",
        "reference list"
    ]

    for page in pages:

        page_text = page.get("text", "")

        for line in page_text.splitlines():

            cleaned = line.strip()

            if not cleaned:
                continue

            heading = re.sub(
                r'^\d+(\.\d+)*\s*',
                '',
                cleaned.lower()
            ).strip(" :.-")

            if heading in headings:

                reference_started = True
                continue

            if reference_started:
                reference_lines.append(cleaned)

    return "\n".join(reference_lines)


# ==========================================
# STEP 3: SPLIT REFERENCES
# ==========================================

def split_reference_entries(reference_text):

    if not reference_text.strip():
        return []

    pattern = re.compile(
        r'(?m)(?=^[A-Z][A-Za-z\'’-]+,'
        r'.{0,150}?\((?:19|20)\d{2}[a-z]?\))'
    )

    positions = [
        match.start()
        for match in pattern.finditer(reference_text)
    ]

    if not positions:
        return [reference_text.strip()]

    references = []

    for i, start in enumerate(positions):

        end = (
            positions[i + 1]
            if i + 1 < len(positions)
            else len(reference_text)
        )

        entry = reference_text[start:end].strip()

        if entry:
            references.append(entry)

    return references


# ==========================================
# STEP 4: EXTRACT REFERENCE DETAILS
# ==========================================

def extract_reference_details(reference):

    year_match = re.search(
        r'\((19|20)\d{2}[a-z]?\)',
        reference
    )

    doi_match = re.search(
        r'(?:https?://doi\.org/|doi:\s*)'
        r'(10\.\d{4,9}/[^\s]+)',
        reference,
        re.IGNORECASE
    )

    year = (
        year_match.group(1) + year_match.group(0)[-1]
        if year_match and year_match.group(0)[-1].isalpha()
        else year_match.group(0).strip("()")
        if year_match
        else None
    )

    doi = (
        doi_match.group(1).rstrip(".,;)")
        if doi_match
        else None
    )

    authors = reference.split("(")[0].strip()

    title = None

    if year_match:

        remaining = reference[year_match.end():].strip()

        title_match = re.search(
            r'^\s*\.?\s*(.+?)(?:\.\s|$)',
            remaining
        )

        if title_match:
            title = title_match.group(1).strip()

    return {
        "raw_reference": reference,
        "authors": authors,
        "year": year,
        "title": title,
        "doi": doi
    }


# ==========================================
# STEP 5: EXTRACT ALL REFERENCES
# ==========================================

def extract_references(pages):

    reference_text = extract_reference_section(pages)

    if not reference_text:
        return []

    raw_references = split_reference_entries(reference_text)

    references = []

    for reference in raw_references:

        details = extract_reference_details(reference)

        references.append(details)

    return references


# ==========================================
# STEP 6: MATCH CITATION WITH REFERENCE
# ==========================================

def match_citation_to_reference(citation, references):

    year_match = re.search(
        r'\b(?:19|20)\d{2}[a-z]?\b',
        citation
    )

    if not year_match:
        return None

    citation_year = year_match.group(0)

    author_match = re.search(
        r'^\s*([A-Za-z\'’-]+)',
        citation
    )

    if not author_match:
        return None

    citation_surname = author_match.group(1).lower()

    for reference in references:

        reference_year = reference.get("year")

        reference_authors = reference.get("authors", "")

        reference_author_match = re.search(
            r'^\s*([A-Za-z\'’-]+)',
            reference_authors
        )

        if not reference_author_match:
            continue

        reference_surname = (
            reference_author_match.group(1).lower()
        )

        if (
            citation_surname == reference_surname
            and citation_year == reference_year
        ):

            return reference

    return None


# ==========================================
# STEP 7: TEST COMPLETE PIPELINE
# ==========================================

if __name__ == "__main__":

    sample_pages = [
        {
            "page": 1,
            "text": """
            Retrieval practice can improve long-term
            retention (Roediger & Karpicke, 2006).

            References

            Roediger, H. L., & Karpicke, J. D. (2006).
            Test-enhanced learning.
            Psychological Science, 17(3), 249-255.

            Hattie, J., & Timperley, H. (2007).
            The Power of Feedback.
            Review of Educational Research, 77(1), 81-112.
            https://doi.org/10.3102/003465430298487
            """
        }
    ]

    print("\n========== CLAIM CITATIONS ==========")

    test_claim = (
        "Retrieval practice can improve long-term "
        "retention (Roediger & Karpicke, 2006)."
    )

    citations = extract_citations(test_claim)

    print(citations)

    print("\n========== REFERENCE EXTRACTION ==========")

    references = extract_references(sample_pages)

    print("Total references:", len(references))

    for reference in references:
        print(reference)

    print("\n========== CITATION REFERENCE MAPPING ==========")

    for citation in citations:

        matched = match_citation_to_reference(
            citation,
            references
        )

        print("\nCitation:", citation)

        if matched:
            print("Matched Reference:", matched["raw_reference"])
        else:
            print("No matching reference found.")
