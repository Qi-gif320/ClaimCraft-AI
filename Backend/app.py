
from flask import Flask, request, render_template, session
from pathlib import Path
from werkzeug.utils import secure_filename
from html import escape
from uuid import uuid4
import os
import sys

# ==========================================
# STEP 1: PROJECT PATHS
# ==========================================

PROJECT_FOLDER = Path("/content/drive/MyDrive/ClaimCraft-AI")
FRONTEND_FOLDER = PROJECT_FOLDER / "Frontend"
BACKEND_FOLDER = PROJECT_FOLDER / "Backend"
UPLOAD_FOLDER = PROJECT_FOLDER / "uploads"

if not PROJECT_FOLDER.exists():
    raise FileNotFoundError("ClaimCraft-AI folder not found!")

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# ==========================================
# STEP 2: FIND PYTHON MODULES
# ==========================================

required_modules = [
    "extract_text.py",
    "claim_detection.py",
    "verification_pipeline.py",
    "evidence_retrieval.py"
]

module_paths = {}

for module_name in required_modules:

    matches = list(PROJECT_FOLDER.rglob(module_name))

    if not matches:
        raise FileNotFoundError(
            f"{module_name} not found in ClaimCraft-AI folder!"
        )

    module_paths[module_name] = matches[0]

    module_folder = str(matches[0].parent)

    if module_folder not in sys.path:
        sys.path.insert(0, module_folder)

# ==========================================
# STEP 3: IMPORT PROJECT MODULES
# ==========================================

from extract_text import extract_text
from claim_detection import detect_claims

from verification_pipeline import (
    extract_citations,
    extract_references,
    match_citation_to_reference
)

from evidence_retrieval import retrieve_evidence
from nli_verification import verify_claim_with_evidence

print("All project modules imported successfully!")

# ==========================================
# STEP 4: FLASK APPLICATION
# ==========================================

app = Flask(
    __name__,
    template_folder=str(FRONTEND_FOLDER)
)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "claimcraft-ai-colab-development-key"
)

app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

ALLOWED_EXTENSIONS = {"pdf", "docx"}

DOCUMENT_STORE = {}

# ==========================================
# STEP 5: FILE VALIDATION
# ==========================================

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# ==========================================
# STEP 6: HOME PAGE
# ==========================================

@app.route("/")
def home():

    return render_template("index.html")


# ==========================================
# STEP 7: DOCUMENT UPLOAD
# ==========================================

@app.route("/upload", methods=["POST"])
def upload():

    if "document" not in request.files:
        return "No document selected!", 400

    file = request.files["document"]

    if file.filename == "":
        return "Please select a document!", 400

    if not allowed_file(file.filename):
        return "Only PDF and DOCX files are allowed!", 400

    filename = secure_filename(file.filename)

    if not filename:
        return "Invalid filename!", 400

    unique_filename = f"{uuid4().hex}_{filename}"
    file_path = UPLOAD_FOLDER / unique_filename

    try:

        file.save(str(file_path))

        # ==========================================
        # TEXT EXTRACTION
        # ==========================================

        print("\n========== TEXT EXTRACTION ==========")

        pages = extract_text(str(file_path))

        if not pages:
            raise ValueError("No document content extracted.")

        print("Total pages:", len(pages))

        # ==========================================
        # CLAIM DETECTION
        # ==========================================

        print("\n========== CLAIM DETECTION ==========")

        claims = detect_claims(pages)

        print("Total claims detected:", len(claims))

        # ==========================================
        # STORE DOCUMENT DATA
        # ==========================================

        document_token = str(uuid4())

        DOCUMENT_STORE[document_token] = {
            "claims": claims,
            "pages": pages
        }

        session["document_token"] = document_token

        # ==========================================
        # CLAIM EXPLORER
        # ==========================================

        claims_html = ""

        if claims:

            for index, item in enumerate(claims):

                claim_text = escape(
                    str(item.get("claim", ""))
                )

                page_number = item.get("page")

                page_display = (
                    "Not available (DOCX)"
                    if page_number is None
                    else str(page_number)
                )

                claims_html += f"""
                <tr>
                    <td>
                        <input
                            type="radio"
                            name="selected_claim"
                            value="{index}"
                            required
                        >
                    </td>

                    <td>{claim_text}</td>

                    <td>{escape(page_display)}</td>
                </tr>
                """

        else:

            claims_html = """
            <tr>
                <td colspan="3">
                    No potential cited claims detected.
                </td>
            </tr>
            """

        if claims:

            selection_form = f"""
            <form action="/verify" method="POST">

                <table>
                    <tr>
                        <th>Select</th>
                        <th>Claim</th>
                        <th>Page Number</th>
                    </tr>

                    {claims_html}

                </table>

                <button type="submit">
                    Verify Selected Claim
                </button>

            </form>
            """

        else:

            selection_form = f"""
            <table>
                <tr>
                    <th>Select</th>
                    <th>Claim</th>
                    <th>Page Number</th>
                </tr>

                {claims_html}

            </table>
            """

        return f"""
        <!DOCTYPE html>
        <html>

        <head>

            <title>ClaimCraft AI - Claim Explorer</title>

            <meta name="viewport" content="width=device-width, initial-scale=1">

            <style>

                body {{
                    font-family: Arial, sans-serif;
                    margin: 40px;
                    background: #f5f6fa;
                    color: #333;
                }}

                h1 {{
                    color: #253858;
                }}

                .summary {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 25px;
                }}

                table {{
                    width: 100%;
                    border-collapse: collapse;
                    background: white;
                }}

                th, td {{
                    border: 1px solid #ddd;
                    padding: 14px;
                    text-align: left;
                    vertical-align: top;
                }}

                th {{
                    background: #253858;
                    color: white;
                }}

                tr:nth-child(even) {{
                    background: #f2f2f2;
                }}

                button {{
                    margin-top: 20px;
                    padding: 12px 22px;
                    background: #253858;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 15px;
                }}

                a {{
                    display: inline-block;
                    margin-top: 20px;
                    color: #253858;
                }}

            </style>

        </head>

        <body>

            <h1>ClaimCraft AI</h1>

            <div class="summary">

                <h2>Document Processed Successfully!</h2>

                <p><strong>File:</strong> {escape(filename)}</p>

                <h2>Total Claims Detected: {len(claims)}</h2>

            </div>

            <h2>Claim Explorer</h2>

            <p>Select one claim that you want to verify.</p>

            {selection_form}

            <a href="/">Upload another document</a>

        </body>

        </html>
        """

    except Exception as error:

        print(
            "PROCESSING ERROR:",
            type(error).__name__,
            error
        )

        return (
            f"Document processing failed: {escape(str(error))}",
            500
        )


# ==========================================
# STEP 8: SELECT CLAIM AND VERIFY
# ==========================================

@app.route("/verify", methods=["POST"])
def verify():

    document_token = session.get("document_token")

    if (
        not document_token
        or document_token not in DOCUMENT_STORE
    ):
        return "Session expired. Please upload your document again.", 400

    document_data = DOCUMENT_STORE[document_token]

    claims = document_data["claims"]
    pages = document_data["pages"]

    selected_index = request.form.get("selected_claim")

    if selected_index is None or not selected_index.isdigit():
        return "Please select a claim first.", 400

    selected_index = int(selected_index)

    if selected_index < 0 or selected_index >= len(claims):
        return "Invalid claim selection.", 400

    selected_claim = claims[selected_index]

    original_claim = str(
        selected_claim.get("claim", "")
    )

    page_number = selected_claim.get("page")

    page_display = (
        "Not available (DOCX)"
        if page_number is None
        else str(page_number)
    )

    print("\n========== SELECTED CLAIM ==========")
    print("Claim:", original_claim)
    print("Page:", page_display)

    # ==========================================
    # STEP 9: CITATION EXTRACTION
    # ==========================================

    print("\n========== CITATION EXTRACTION ==========")

    citations = extract_citations(original_claim)

    print("Extracted citations:", citations)

    # ==========================================
    # STEP 10: REFERENCE LIST EXTRACTION
    # ==========================================

    print("\n========== REFERENCE LIST EXTRACTION ==========")

    references = extract_references(pages)

    print("Total references extracted:", len(references))

    # ==========================================
    # STEP 11: CITATION-REFERENCE MAPPING
    # ==========================================

    print("\n========== CITATION REFERENCE MAPPING ==========")

    mapping_results = []

    for citation in citations:

        matched_reference = match_citation_to_reference(
            citation,
            references
        )

        mapping_results.append({
            "citation": citation,
            "reference": matched_reference
        })

        print("\nCitation:", citation)

        if matched_reference:

            print(
                "Matched reference:",
                matched_reference["raw_reference"]
            )

        else:

            print("No matching reference found.")

    # ==========================================
    # STEP 12: EVIDENCE RETRIEVAL
    # ==========================================

    print("\n========== EVIDENCE RETRIEVAL ==========")

    evidence_results = []

    for result in mapping_results:

        matched_reference = result["reference"]

        if matched_reference:

            print(
                "\nRetrieving evidence for:",
                matched_reference.get("title")
            )

            try:

                evidence_result = retrieve_evidence(
                    original_claim,
                    matched_reference,
                    top_k=3
                )

                # Run DeBERTa NLI on retrieved evidence
                retrieved_passages = evidence_result.get("evidence", [])

                if retrieved_passages:
                    print("Running DeBERTa NLI verification...")

                    nli_results = verify_claim_with_evidence(
                        original_claim,
                        retrieved_passages
                    )

                    evidence_result["nli_results"] = nli_results

                    for nli_item in nli_results:
                        print(
                            "NLI Result:",
                            nli_item.get("status")
                        )

                evidence_results.append({
                    "citation": result["citation"],
                    "result": evidence_result
                })

                print(
                    "Evidence retrieval status:",
                    evidence_result.get("status")
                )

            except Exception as error:

                print("Evidence retrieval error:", error)

                evidence_results.append({
                    "citation": result["citation"],
                    "result": {
                        "status": "error",
                        "message": str(error)
                    }
                })

        else:

            evidence_results.append({
                "citation": result["citation"],
                "result": {
                    "status": "reference_not_found",
                    "message": "No matching reference was found."
                }
            })

    # ==========================================
    # STEP 13: PREPARE CITATION HTML
    # ==========================================

    citation_html = ""

    if citations:

        for result in mapping_results:

            citation = escape(result["citation"])

            matched = result["reference"]

            if matched:

                full_reference = escape(
                    str(matched.get("raw_reference", ""))
                )

                year = escape(
                    str(matched.get("year") or "Not identified")
                )

                title = escape(
                    str(matched.get("title") or "Not identified")
                )

                doi = matched.get("doi")

                doi_display = (
                    f'<p><strong>DOI:</strong> {escape(str(doi))}</p>'
                    if doi
                    else '<p><strong>DOI:</strong> Not found in reference</p>'
                )

                citation_html += f"""
                <div class="citation">

                    <h3>In-text Citation: {citation}</h3>

                    <p><strong>Status:</strong> Matching reference found</p>

                    <p><strong>Year:</strong> {year}</p>

                    <p><strong>Title:</strong> {title}</p>

                    {doi_display}

                    <p>
                        <strong>Matched Reference:</strong><br>
                        {full_reference}
                    </p>

                </div>
                """

            else:

                citation_html += f"""
                <div class="citation">

                    <h3>In-text Citation: {citation}</h3>

                    <p>
                        <strong>Status:</strong>
                        No matching reference found.
                    </p>

                </div>
                """

    else:

        citation_html = """
        <div class="citation">
            No citation extracted from selected claim.
        </div>
        """

    # ==========================================
    # STEP 14: PREPARE EVIDENCE HTML
    # ==========================================

    evidence_html = ""

    for item in evidence_results:

        result = item["result"]

        evidence_html += f"""
        <div class="citation">

            <h3>Research Paper Evidence</h3>

            <p>
                <strong>Associated Citation:</strong>
                {escape(str(item["citation"]))}
            </p>

            <p>
                <strong>Paper:</strong>
                {escape(str(result.get("paper_title", "Not identified")))}
            </p>

            <p>
                <strong>Retrieval Status:</strong>
                {escape(str(result.get("status", "Unknown")))}
            </p>
        """

        if result.get("doi"):

            evidence_html += f"""
            <p>
                <strong>DOI:</strong>
                {escape(str(result["doi"]))}
            </p>
            """

        if result.get("paper_url"):

            evidence_html += f"""
            <p>
                <a href="{escape(str(result["paper_url"]))}"
                   target="_blank">
                    Open Research Paper PDF
                </a>
            </p>
            """

        retrieved_passages = result.get("evidence", [])
        nli_results = result.get("nli_results", [])

        if retrieved_passages:

            for number, evidence in enumerate(
                retrieved_passages,
                start=1
            ):

                nli = (
                    nli_results[number - 1]
                    if number <= len(nli_results)
                    else {}
                )

                nli_status = escape(
                    str(nli.get("status", "Not evaluated"))
                )

                evidence_html += f"""
                <div class="evidence">

                    <h4>Evidence Passage {number}</h4>

                    <p>
                        <strong>PDF Page:</strong>
                        {escape(str(evidence.get("page", "Unknown")))}
                    </p>

                    <p>
                        <strong>Similarity Score:</strong>
                        {escape(str(evidence.get("similarity_score", "N/A")))}
                    </p>

                    <p>
                        <strong>Evidence Text:</strong><br>
                        {escape(str(evidence.get("evidence", "")))}
                    </p>

                    <hr>

                    <h4>AI Verification Result</h4>

                    <p>
                        <strong>NLI Status:</strong>
                        {nli_status}
                    </p>

                    <p>
                        <strong>Entailment Score:</strong>
                        {escape(str(nli.get("entailment_score", "N/A")))}
                    </p>

                    <p>
                        <strong>Contradiction Score:</strong>
                        {escape(str(nli.get("contradiction_score", "N/A")))}
                    </p>

                    <p>
                        <strong>Neutral Score:</strong>
                        {escape(str(nli.get("neutral_score", "N/A")))}
                    </p>

                </div>
                """

        elif result.get("message"):

            evidence_html += f"""
            <p>
                <strong>Message:</strong>
                {escape(str(result["message"]))}
            </p>
            """

        evidence_html += "</div>"

    if not evidence_results:

        evidence_html = """
        <div class="citation">
            Evidence retrieval could not start because no matching
            citation-reference pair was available.
        </div>
        """

    # ==========================================
    # STEP 15: REFERENCE EXTRACTION SUMMARY
    # ==========================================

    if references:

        reference_summary = f"""
        <p>
            <strong>Total references extracted:</strong>
            {len(references)}
        </p>
        """

    else:

        reference_summary = """
        <p>
            No References section was detected in the uploaded document.
        </p>
        """

    # ==========================================
    # STEP 16: DISPLAY RESULTS
    # ==========================================

    return f"""
    <!DOCTYPE html>
    <html>

    <head>

        <title>ClaimCraft AI - Verification Results</title>

        <meta name="viewport" content="width=device-width, initial-scale=1">

        <style>

            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
                background: #f5f6fa;
                color: #333;
            }}

            h1 {{
                color: #253858;
            }}

            .result {{
                background: white;
                padding: 25px;
                border-radius: 8px;
                margin-top: 20px;
            }}

            .citation {{
                background: #eaf4ff;
                padding: 18px;
                border-radius: 6px;
                margin-top: 18px;
                overflow-wrap: anywhere;
            }}

            .evidence {{
                background: white;
                padding: 15px;
                border-radius: 6px;
                margin-top: 15px;
                border-left: 4px solid #253858;
            }}

            button {{
                margin-top: 20px;
                padding: 12px 22px;
                background: #253858;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
            }}

            a {{
                display: inline-block;
                margin-top: 10px;
                color: #253858;
            }}

            hr {{
                margin-top: 25px;
                margin-bottom: 25px;
            }}

        </style>

    </head>

    <body>

        <h1>ClaimCraft AI</h1>

        <div class="result">

            <h2>Selected Claim Received!</h2>

            <p>
                <strong>Claim:</strong>
                {escape(original_claim)}
            </p>

            <p>
                <strong>Page:</strong>
                {escape(page_display)}
            </p>

            <hr>

            <h2>Citation and Reference Mapping</h2>

            {reference_summary}

            {citation_html}

            <hr>

            <h2>Retrieved Research Evidence</h2>

            {evidence_html}

            <hr>

            <p>
                <strong>Important Note:</strong>
                MiniLM retrieves passages based on semantic similarity.
                The similarity score measures relevance, not whether
                the claim is Supported or Refuted.
                DeBERTa NLI evaluates retrieved evidence passages.
                Results depend on the quality and relevance of the
                retrieved research evidence.
            </p>

        </div>

        <a href="/">Upload another document</a>

    </body>

    </html>
    """


# ==========================================
# STEP 17: FILE SIZE ERROR
# ==========================================

@app.errorhandler(413)
def file_too_large(error):

    return "File size exceeds the 20 MB limit!", 413


# ==========================================
# STEP 18: RUN FLASK
# ==========================================

if __name__ == "__main__":

    print("\nClaimCraft AI Flask Server Starting...")
    print("Project folder:", PROJECT_FOLDER)
    print("Backend modules connected successfully!")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False
    )
