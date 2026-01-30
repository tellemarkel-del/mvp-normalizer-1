import os
import re
import json
import pdfplumber
import pytesseract
import pandas as pd
import openai
from pdf2image import convert_from_path
from config import OPENAI_API_KEY

# OpenAI client v1.x
client = openai.OpenAI(api_key=OPENAI_API_KEY)

OUTPUT_FOLDER = "outputs"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ---------- HELPERS ----------

def extract_text_digital_pdf(path):
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

def extract_text_scanned_pdf(path):
    images = convert_from_path(path, dpi=300)
    text = ""
    for img in images:
        text += pytesseract.image_to_string(img)
    return text

def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def pre_extract_fields(text):
    data = {}
    date_match = re.search(r'\b\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4}\b', text)
    total_match = re.search(r'(total|amount due)[^\d]*([\d\.,]+)', text, re.I)
    vat_match = re.search(r'(vat|iva)[^\d]*([\d\.,]+)', text, re.I)

    data["Date"] = date_match.group(0) if date_match else ""
    data["Total"] = total_match.group(2) if total_match else ""
    data["VAT"] = vat_match.group(2) if vat_match else ""

    return data

def normalize_with_gpt(text, pre_data):
    prompt = f"""
You are an invoice normalization engine.

Invoice text:
{text}

Pre-extracted data:
{json.dumps(pre_data)}

Return ONLY valid JSON with these fields:
Supplier, Date, Total, VAT

Rules:
- Supplier must be the company issuing the invoice
- Date format: YYYY-MM-DD if possible
- Numbers without currency symbols
"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    return json.loads(response.choices[0].message.content)

# ---------- MAIN PROCESS ----------

def process_documents(filepaths):
    results = []

    for path in filepaths:
        filename = os.path.basename(path)

        # Step 1: try digital PDF
        text = extract_text_digital_pdf(path)

        # Step 2: fallback to OCR
        if not text.strip():
            text = extract_text_scanned_pdf(path)

        text = clean_text(text)

        # Step 3: deterministic pre-extraction
        pre_data = pre_extract_fields(text)

        # Step 4: GPT normalization
        structured = normalize_with_gpt(text[:6000], pre_data)

        structured["FileName"] = filename
        results.append(structured)

    df = pd.DataFrame(results)
    output_path = os.path.join(OUTPUT_FOLDER, "invoice_normalized.xlsx")
    df.to_excel(output_path, index=False)

    return output_path
