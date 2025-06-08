from fastapi import FastAPI, UploadFile, File, HTTPException
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
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# File paths
KEYWORDS_CSV = "keywords.csv"
SUBCATEGORY_CATEGORY_CSV = "subcategory_to_category.csv"
MODEL_FILE = "model.pkl"
VECTORIZER_FILE = "vectorizer.pkl"

# Initialize data structures
subcategory_keywords = {}
subcategory_to_category = {}
model = None
vectorizer = None

def load_keywords():
    """Load keyword mappings from CSV"""
    global subcategory_keywords
    try:
        with open(KEYWORDS_CSV, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                subcategory = row["Subcategory"].strip()
                keywords_str = row["Keywords"].strip()
                keywords = [kw.strip().lower() for kw in keywords_str.split(";") if kw.strip()]
                subcategory_keywords[subcategory] = keywords
        print(f"Loaded keywords for subcategories: {list(subcategory_keywords.keys())}")
    except Exception as e:
        print(f"Error loading keywords: {e}")
        # Fallback keywords
        subcategory_keywords = {
            "Paystub": ["ytd", "employment insurance", "pay period"],
            "T4": ["statement of remuneration", "qpp contributions"],
            "NOA": ["notice of assessment"],
            "RBC Chequing": ["rbc personal banking"],
            "RBC Savings": ["rbc personal savings"]
        }

def load_category_mappings():
    """Load subcategory to category mappings"""
    global subcategory_to_category
    try:
        with open(SUBCATEGORY_CATEGORY_CSV, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                subcategory = row["subcategory"].strip()
                category = row["category"].strip()
                subcategory_to_category[subcategory] = category
        print(f"Loaded category mappings: {subcategory_to_category}")
    except Exception as e:
        print(f"Error loading category mappings: {e}")
        # Fallback mappings
        subcategory_to_category = {
            "Paystub": "Income",
            "T4": "Income", 
            "NOA": "Income",
            "RBC Chequing": "Down Payment",
            "RBC Savings": "Down Payment",
            "Passport": "ID"
        }

def load_ml_models():
    """Load ML model and vectorizer if they exist"""
    global model, vectorizer
    try:
        if os.path.exists(MODEL_FILE) and os.path.exists(VECTORIZER_FILE):
            model = joblib.load(MODEL_FILE)
            vectorizer = joblib.load(VECTORIZER_FILE)
            print("ML models loaded successfully")
        else:
            print("ML model files not found - using rule-based classification only")
    except Exception as e:
        print(f"Error loading ML models: {e}")

# Load all configurations on startup
load_keywords()
load_category_mappings()
load_ml_models()

# ---- NLP EXTRACTORS ----

def extract_name(text: str):
    """Extract client name from document text"""
    # Multiple patterns for name extraction
    patterns = [
        r"(?:Client|Prepared for)[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"(?:Name|Employee)[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s+(?:Statement|Report|Summary))"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    
    return "Client"

def extract_date(text: str):
    """Extract the most recent date from text"""
    # Look for various date formats
    date_patterns = [
        r"(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])",  # YYYY-MM-DD
        r"(20\d{2})[-/](0?[1-9]|1[0-2])",  # YYYY-MM
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d{2})",
        r"(20\d{2})"  # Just year
    ]
    
    dates = []
    for pattern in date_patterns:
        matches = re.findall(pattern, text)
        if matches:
            if isinstance(matches[0], tuple):
                # Multiple groups - reconstruct date
                if len(matches[0]) == 3:  # YYYY-MM-DD
                    year, month, day = matches[-1]
                    dates.append(f"{year}_{month.zfill(2)}")
                elif len(matches[0]) == 2:  # YYYY-MM
                    year, month = matches[-1]
                    dates.append(f"{year}_{month.zfill(2)}")
                else:
                    dates.append(matches[-1][0])
            else:
                dates.append(matches[-1])
    
    return dates[-1] if dates else None

def extract_amount(text: str):
    """Extract monetary amounts from text"""
    # Look for balance, total, or amount patterns
    patterns = [
        r"(?i)(?:Total\s+|Final\s+|Current\s+)?(?:Balance|Amount)[^\d]*\$?([0-9,]+(?:\.\d{2})?)",
        r"(?i)Balance[^\d]*\$?([0-9,]+(?:\.\d{2})?)",
        r"\$([0-9,]+(?:\.\d{2})?)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            amt_str = match.group(1).replace(",", "")
            try:
                amt = float(amt_str)
                if amt >= 1000:
                    return f"${int(amt // 1000)}K"
                else:
                    return f"${int(amt)}"
            except ValueError:
                continue
    
    return "$0"

def extract_account_number(text: str):
    """Extract account number from text"""
    patterns = [
        r"(?:Account\s+Number|Acc\s*#|Account)[^\d]*(\d{3,})",
        r"#(\d{3,})",
        r"(\d{4,})"  # Any sequence of 4+ digits
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return "#" + match.group(1)[-3:]  # Last 3 digits
    
    return "#000"

# ---- CLASSIFICATION ----

def classify_subcategory(text: str):
    """Classify document subcategory using hybrid approach"""
    text_lower = text.lower()

    # 1. Rule-based keyword matching (primary)
    for subcat, keywords in subcategory_keywords.items():
        if any(kw in text_lower for kw in keywords):
            print(f"Classified as {subcat} using keyword matching")
            return subcat

    # 2. ML-based fallback (if models are available)
    if model and vectorizer:
        try:
            X = vectorizer.transform([text])
            predicted = model.predict(X)[0]
            print(f"Classified as {predicted} using ML model")
            return predicted
        except Exception as e:
            print(f"Error in ML classification: {e}")

    # 3. Default fallback
    print("Using default classification: Unknown")
    return "Unknown"

def validate_id_document(text: str):
    """Basic ID document validation"""
    id_indicators = [
        "passport", "driver", "license", "identification", 
        "birth certificate", "sin", "social insurance"
    ]
    
    text_lower = text.lower()
    has_id_content = any(indicator in text_lower for indicator in id_indicators)
    
    # Check for common ID patterns
    has_numbers = bool(re.search(r'\d{4,}', text))  # ID numbers
    has_dates = bool(re.search(r'20\d{2}', text))   # Expiry dates
    
    return {
        "is_valid_id": has_id_content and (has_numbers or has_dates),
        "id_type": next((ind for ind in id_indicators if ind in text_lower), "unknown"),
        "has_expiry": has_dates,
        "confidence": 0.8 if has_id_content else 0.3
    }

def check_document_date_validity(text: str, max_days_old: int = 90):
    """Check if document is within acceptable date range"""
    from datetime import datetime, timedelta
    
    date_str = extract_date(text)
    if not date_str:
        return {"is_valid": False, "reason": "No date found"}
    
    try:
        # Parse extracted date
        if "_" in date_str:
            year, month = date_str.split("_")
            doc_date = datetime(int(year), int(month), 1)
        else:
            doc_date = datetime(int(date_str), 1, 1)
        
        # Check if within acceptable range
        max_age = datetime.now() - timedelta(days=max_days_old)
        is_valid = doc_date >= max_age
        
        return {
            "is_valid": is_valid,
            "document_date": date_str,
            "days_old": (datetime.now() - doc_date).days,
            "max_allowed_days": max_days_old
        }
    except Exception as e:
        return {"is_valid": False, "reason": f"Date parsing error: {e}"}

# ---- MAIN CLASSIFICATION ENDPOINT ----

@app.post("/classify")
async def classify_files(files: List[UploadFile] = File(...)):
    """Main endpoint for document classification"""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    
    results = {}
    
    for file in files:
        try:
            contents = await file.read()
            text = ""
            
            # ---- Extract text based on file type ----
            if file.filename.lower().endswith(".pdf"):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(contents)
                    tmp_path = tmp.name
                
                try:
                    with pdfplumber.open(tmp_path) as pdf:
                        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                finally:
                    os.unlink(tmp_path)
                    
            elif file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
                try:
                    image = Image.open(io.BytesIO(contents))
                    text = pytesseract.image_to_string(image)
                except Exception as e:
                    text = f"Error processing image: {e}"
            else:
                text = "Unsupported file format"

            if not text or text.strip() == "":
                text = "No text extracted from document"

            # ---- Classification ----
            subcategory = classify_subcategory(text)
            category = subcategory_to_category.get(subcategory, "Other")

            # ---- Metadata Extraction ----
            name = extract_name(text)
            date = extract_date(text)
            
            # ---- Additional Validations ----
            id_validation = None
            date_validation = None
            
            if category == "ID":
                id_validation = validate_id_document(text)
            
            if category in ["Income", "Down Payment"]:
                date_validation = check_document_date_validity(text)

            # ---- File Renaming Logic ----
            if category == "Income":
                renamed = f"{name}_Income_{subcategory}_{date or 'Undated'}"
            elif category == "Down Payment":
                amount = extract_amount(text)
                acc = extract_account_number(text)
                renamed = f"{name}_DP_{amount}_{subcategory}_{acc}"
            elif category == "ID":
                renamed = f"{name}_ID_{subcategory}"
            else:
                renamed = f"{name}_Other_{os.path.splitext(file.filename)[0]}"

            # ---- Build Result ----
            result = {
                "category": category,
                "subcategory": subcategory,
                "renamed": renamed,
                "text": text[:1000],  # Preview
                "metadata": {
                    "client_name": name,
                    "date": date,
                    "extracted_amount": extract_amount(text) if category == "Down Payment" else None,
                    "account_number": extract_account_number(text) if category == "Down Payment" else None
                }
            }
            
            # Add validation results if applicable
            if id_validation:
                result["id_validation"] = id_validation
            if date_validation:
                result["date_validation"] = date_validation

            results[file.filename] = result

        except Exception as e:
            results[file.filename] = {
                "category": "Error",
                "subcategory": "Processing Failed",
                "renamed": file.filename,
                "text": f"Error processing file: {str(e)}",
                "error": str(e)
            }

    return results

# ---- Health Check ----
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "keywords_loaded": len(subcategory_keywords),
        "categories_loaded": len(subcategory_to_category),
        "ml_model_available": model is not None
    }

# ---- Get Configuration ----
@app.get("/config")
async def get_config():
    return {
        "subcategories": list(subcategory_keywords.keys()),
        "categories": list(set(subcategory_to_category.values())),
        "mappings": subcategory_to_category
    }
