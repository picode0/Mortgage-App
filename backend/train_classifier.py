import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
import joblib

df = pd.read_csv("training_data.csv")

texts = df["text_sample"].tolist()
labels = df["subcategory"].tolist()

pipeline = Pipeline([
    ('tfidf', TfidfVectorizer(max_features=5000, ngram_range=(1,2))),
    ('clf', LogisticRegression(max_iter=1000)),
])

pipeline.fit(texts, labels)

joblib.dump(pipeline, "models/subcategory_classifier.joblib")

print("Model trained and saved!")
