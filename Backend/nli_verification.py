
from transformers import pipeline

MODEL_NAME = "cross-encoder/nli-deberta-v3-base"

_nli_model = None


def get_nli_model():
    global _nli_model

    if _nli_model is None:
        print("Loading DeBERTa NLI model...")

        _nli_model = pipeline(
            "text-classification",
            model=MODEL_NAME,
            tokenizer=MODEL_NAME,
            top_k=None
        )

        print("DeBERTa model loaded successfully!")

    return _nli_model


def normalize_prediction(raw_prediction):
    """
    Converts different Transformers output formats
    into a consistent list of prediction dictionaries.
    """

    while isinstance(raw_prediction, list) and len(raw_prediction) == 1:
        if isinstance(raw_prediction[0], list):
            raw_prediction = raw_prediction[0]
        else:
            break

    if isinstance(raw_prediction, dict):
        raw_prediction = [raw_prediction]

    if not isinstance(raw_prediction, list):
        raise ValueError(
            f"Unexpected prediction format: {type(raw_prediction)}"
        )

    if not all(isinstance(item, dict) for item in raw_prediction):
        raise ValueError(
            f"Unexpected prediction contents: {raw_prediction}"
        )

    return raw_prediction


def verify_claim_with_evidence(claim, evidence_passages):

    model = get_nli_model()
    results = []

    for passage in evidence_passages:

        evidence_text = passage["evidence"]

        raw_prediction = model({
            "text": evidence_text,
            "text_pair": claim
        })

        predictions = normalize_prediction(raw_prediction)

        scores = {
            item["label"].lower(): float(item["score"])
            for item in predictions
        }

        # Read NLI scores
        entailment = scores.get("entailment", 0)
        contradiction = scores.get("contradiction", 0)
        neutral = scores.get("neutral", 0)

        # Classify the evidence
        if entailment >= 0.70 and contradiction >= 0.70:
            status = "Insufficient Evidence"

        elif entailment >= 0.70:
            status = "Supported"

        elif contradiction >= 0.70:
            status = "Refuted"

        else:
            status = "Insufficient Evidence"

        results.append({
            "evidence": evidence_text,
            "page": passage.get("page"),
            "similarity_score": passage.get("similarity_score"),
            "entailment_score": entailment,
            "contradiction_score": contradiction,
            "neutral_score": neutral,
            "status": status
        })

    return results
