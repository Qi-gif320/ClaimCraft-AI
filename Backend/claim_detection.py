
import re
from transformers import pipeline

MODEL_NAME = "MoritzLaurer/deberta-v3-xsmall-zeroshot-v1.1-all-33"

CLAIM_LABEL = (
    "a factual research statement that can be "
    "verified using scientific evidence"
)

NON_CLAIM_LABEL = (
    "general background information, a definition, "
    "an opinion, or an instruction"
)

LABELS = [CLAIM_LABEL, NON_CLAIM_LABEL]

THRESHOLD = 0.55

classifier = None


# Load AI model
def load_model():

    global classifier

    if classifier is None:

        print("\nLoading ClaimCraft AI model...")

        classifier = pipeline(
            "zero-shot-classification",
            model=MODEL_NAME,
            device=-1
        )

        print("Model loaded successfully!")

    return classifier


# Check author-year citations
def has_citation(sentence):

    parenthetical = re.search(
        r'\([^()]*\b(?:19|20)\d{2}[a-z]?\b[^()]*\)',
        sentence
    )

    narrative = re.search(
        r'\b[A-Z][A-Za-z\'’-]+'
        r'(?:\s+(?:and|&)\s+[A-Z][A-Za-z\'’-]+'
        r'|\s+et\s+al\.)?'
        r'\s*\((?:19|20)\d{2}[a-z]?\)',
        sentence
    )

    return bool(parenthetical or narrative)


# Split text into sentences
def split_sentences(text):

    # Protect et al. from sentence splitting
    text = re.sub(
        r'\bet al\.',
        'et al<ETAL_DOT>',
        text
    )

    sentences = re.split(
        r'(?<=[.!?])\s+',
        text.strip()
    )

    cleaned_sentences = []

    for sentence in sentences:

        sentence = sentence.replace(
            'et al<ETAL_DOT>',
            'et al.'
        ).strip()

        if len(sentence.split()) >= 6:
            cleaned_sentences.append(sentence)

    return cleaned_sentences


# Main claim detection function
def detect_claims(pages, threshold=THRESHOLD):

    detected_claims = []

    claim_id = 1

    print("\n========== CLAIMCRAFT AI DEBUGGING ==========")

    for page in pages:

        page_number = page["page"]

        page_text = page["text"]

        print(f"\n\n========== PAGE {page_number} ==========")

        # Step 1: Sentence extraction
        sentences = split_sentences(page_text)

        print("Total sentences:", len(sentences))

        # Step 2: Citation filtering
        cited_sentences = []

        for sentence in sentences:

            if has_citation(sentence):

                cited_sentences.append(sentence)

        print("Cited sentences:", len(cited_sentences))

        for sentence in cited_sentences:

            print("\n[CITATION FOUND]")
            print(sentence)

        if not cited_sentences:

            print("No cited sentences found on this page.")

            continue

        # Step 3: Load model
        model = load_model()

        # Step 4: Classify cited sentences
        for start in range(0, len(cited_sentences), 8):

            batch = cited_sentences[start:start + 8]

            results = model(
                batch,
                candidate_labels=LABELS,
                hypothesis_template="This sentence is {}.",
                multi_label=False
            )

            for sentence, result in zip(batch, results):

                scores = dict(
                    zip(result["labels"], result["scores"])
                )

                confidence = scores.get(CLAIM_LABEL, 0)

                print("\n[AI CLASSIFICATION]")
                print("Sentence:", sentence)
                print("Claim confidence:", round(float(confidence), 3))

                if confidence >= threshold:

                    print("Decision: ACCEPTED")

                    detected_claims.append({

                        "id": claim_id,

                        "claim": sentence,

                        "page": page_number

                    })

                    claim_id += 1

                else:

                    print("Decision: REJECTED")

        print("\nClaims detected on this page:",
              sum(1 for item in detected_claims
                  if item["page"] == page_number))

    print("\n========== FINAL RESULTS ==========")

    print("Total potential claims:", len(detected_claims))

    for item in detected_claims:

        print(
            f"Claim: {item['claim']} | Page: {item['page']}"
        )

    return detected_claims
