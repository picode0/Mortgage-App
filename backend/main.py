from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import pdfplumber
import pytesseract
from PIL import Image
import io
import os
import tempfile
import re
import csv
import joblib
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load training data
KEYWORD_CSV = "ml_training_data.csv"
MODEL_FILE = "model.pkl"
VECTORIZER_FILE = "vectorizer.pkl"

# Load ML model and vectorizer
model = joblib.load(MODEL_FILE)
vectorizer = joblib.load(VECTORIZER_FILE)

# Load keyword mappings
subcategory_keywords = {}
subcategory_to_category = {}

with open(KEYWORD_CSV, newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        sub = row["subcategory"]
        cat = row["category"]
        keywords = [kw.strip().lower() for kw in row["keywords"].split(";") if kw.strip()]
        subcategory_keywords[sub] = keywords
        subcategory_to_category[sub] = cat

# ---- NLP EXTRACTORS ----

def extract_name(text: str):
    # crude name extraction - assumes format: "Client: John Smith" or "Prepared for John"
    match = re.search(r"(?:Client|Prepared for)[:\s]*([A-Z][a-z]+)", text)
    return match.group(1) if match else "Client"

def extract_date(text: str):
    # Extracts the most recent YYYY-MM or YYYY date from text
    match = re.findall(r"(20\d{2})([-/](0?[1-9]|1[0-2]))?", text)
    if match:
        year, _, month = match[-1]
        return f"{year}_{month.zfill(2)}" if month else year
    return None

def extract_amount(text: str):
    match = re.search(r"(?i)(Total\s+)?(?:Balance|Amount)[^\d]*\$?([0-9,]+(?:\.\d{2})?)", text)
    if match:
        amt = match.group(2).replace(",", "")
        return f"${int(float(amt)) // 1000}K"
    return "$0"

def extract_account_number(text: str):
    match = re.search(r"(?:Account\s+Number|Acc\s*#)[^\d]*(\d{3,})", text)
    if match:
        return "#" + match.group(1)[-3:]
    return "#000"

# ---- CLASSIFICATION ----

def classify_subcategory(text: str):
    text_lower = text.lower()

    # 1. Rule-based keyword match
    for subcat, keywords in subcategory_keywords.items():
        if any(kw in text_lower for kw in keywords):
            return subcat

    # 2. ML-based fallback
    X = vectorizer.transform([text])
    return model.predict(X)[0]

# ---- FILE HANDLER ----

@app.post("/classify")
async def classify_files(files: List[UploadFile] = File(...)):
    results = {}

    for file in files:
        contents = await file.read()
        text = ""
        renamed = ""
        category = "Other"
        subcategory = "Unknown"

        try:
            # ---- Extract text ----
            if file.filename.lower().endswith(".pdf"):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(contents)
                    tmp_path = tmp.name
                with pdfplumber.open(tmp_path) as pdf:
                    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                os.unlink(tmp_path)
            else:
                image = Image.open(io.BytesIO(contents))
                text = pytesseract.image_to_string(image)

            # ---- Classification ----
            subcategory = classify_subcategory(text)
            category = subcategory_to_category.get(subcategory, "Other")

            # ---- Metadata ----
            name = extract_name(text)
            date = extract_date(text)

            if category == "Income":
                renamed = f"{name}_{category}_{subcategory}_{date or 'Undated'}"

            elif category == "Down Payment":
                amount = extract_amount(text)
                acc = extract_account_number(text)
                renamed = f"{name}_DP_{amount}_{subcategory}_{acc}"

            elif category == "ID":
                renamed = f"{name}_ID_{subcategory}"

            else:
                renamed = f"{name}_Other_{file.filename}"

        except Exception as e:
            text = f"Error reading file: {e}"
            renamed = file.filename

        results[file.filename] = {
            "category": category,
            "subcategory": subcategory,
            "renamed": renamed,
            "text": text[:1000]  # trimmed preview
        }

    return results
