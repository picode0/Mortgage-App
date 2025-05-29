# retrain_model.py
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
import joblib

# Load and prepare training data
csv_path = "ml_training_data.csv"
df = pd.read_csv(csv_path)
df.dropna(subset=["text", "subcategory"], inplace=True)

X = df["text"]
y = df["subcategory"]

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Build pipeline
pipeline = Pipeline([
    ("tfidf", TfidfVectorizer(max_features=3000, stop_words="english")),
    ("clf", MultinomialNB()),
])

# Train
pipeline.fit(X_train, y_train)

# Save model
joblib.dump(pipeline, "model.pkl")

# Evaluate
acc = pipeline.score(X_test, y_test)
print(f"Model accuracy: {acc:.2f}")
