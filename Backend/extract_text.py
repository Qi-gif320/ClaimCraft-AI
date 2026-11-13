
import fitz
from docx import Document
from pathlib import Path


def extract_text(file_path):

    file_path = Path(file_path)
    extension = file_path.suffix.lower()

    extracted_pages = []

    # PDF extraction
    if extension == ".pdf":

        pdf_document = fitz.open(file_path)

        for page_number, page in enumerate(pdf_document, start=1):

            page_text = page.get_text("text")

            extracted_pages.append({
                "page": page_number,
                "text": page_text
            })

        pdf_document.close()

    # DOCX extraction
    elif extension == ".docx":

        document = Document(file_path)

        full_text = "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        )

        extracted_pages.append({
            "page": None,
            "text": full_text
        })

    else:
        raise ValueError("Only PDF and DOCX files are supported.")

    return extracted_pages


if __name__ == "__main__":
    print("ClaimCraft AI - Text Extraction Module")
