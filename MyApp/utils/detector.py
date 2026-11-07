import os
import hashlib
import warnings
from pathlib import Path
import joblib
import PyPDF2
import docx
import pptx

def extract_text(file_path: str) -> str:
    """Extract text from PDF, DOCX, PPTX, or TXT file."""
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    try:
        if ext == '.txt':
            for encoding in ['utf-8', 'latin-1', 'utf-16']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        text = f.read()
                    break
                except UnicodeDecodeError:
                    continue
        elif ext == '.pdf':
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                pages_text = []
                for page in reader.pages:
                    t = page.extract_text()
                    if t:
                        pages_text.append(t)
                text = "\n".join(pages_text)
        elif ext == '.docx':
            doc = docx.Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
        elif ext == '.pptx':
            prs = pptx.Presentation(file_path)
            text_runs = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        text_runs.append(shape.text)
            text = "\n".join(text_runs)
    except Exception as e:
        print(f"Error extracting text from {file_path}: {e}")
    return text.strip()

class MockAIDetector:
    """Mock AI detector for testing when the actual model is not available."""
    
    def predict(self, file_path: str) -> dict:
        """Return simulated detection results based on file content."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read(10000)  # Read first 10KB
            
            # Simple heuristic: use file hash to generate consistent results
            file_hash = hashlib.md5(content).hexdigest()
            hash_int = int(file_hash, 16)
            
            # Simulate AI detection with ~30% AI detection rate
            is_ai = (hash_int % 10) < 3
            confidence = 0.65 + (hash_int % 35) / 100  # Between 0.65 and 1.0
            
            return {
                'label': 'AI' if is_ai else 'Human',
                'confidence': round(confidence, 2),
                'note': 'Mock detection - actual model not loaded'
            }
        except Exception as e:
            return {
                'label': 'Unknown',
                'confidence': 0.0,
                'error': f'Error reading file: {str(e)}'
            }

def _load_model_and_vectorizer():
    try:
        from django.conf import settings
        model_path = Path(settings.DETECTOR_MODEL_PATH)
        vec_path = model_path.parent / 'tfidf_vectorizer.pkl'
    except Exception:
        models_dir = Path(__file__).resolve().parent.parent.parent / 'models'
        model_path = models_dir / 'ai_detector_model.pkl'
        vec_path = models_dir / 'tfidf_vectorizer.pkl'
    
    if model_path.is_file() and vec_path.is_file():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = joblib.load(model_path)
                vec = joblib.load(vec_path)
                return model, vec
        except Exception as e:
            print(f"Error loading models: {e}")
            return None, None
    return None, None

_model, _vectorizer = _load_model_and_vectorizer()

def predict(file_path: str) -> dict:
    """Run the AI detector on the given file.

    Parameters
    ----------
    file_path: str
        Path to the uploaded file (PDF, DOCX, PPTX, TXT).

    Returns
    -------
    dict
        A dictionary with keys ``label`` ("AI" or "Human") and ``confidence`` (float 0-1).
    """
    if _model is not None and _vectorizer is not None:
        try:
            text = extract_text(file_path)
            if not text:
                # Fallback to mock if no text could be extracted
                return MockAIDetector().predict(file_path)
                
            features = _vectorizer.transform([text])
            proba = _model.predict_proba(features)[0]
            
            # Class 0: Human, Class 1: AI
            prob_ai = proba[1]
            prob_human = proba[0]
            
            label = 'AI' if prob_ai > 0.5 else 'Human'
            confidence = prob_ai if label == 'AI' else prob_human
            
            return {
                'label': label,
                'confidence': round(float(confidence), 2)
            }
        except Exception as e:
            print(f"Error predicting with real model: {e}")
            return MockAIDetector().predict(file_path)
    else:
        return MockAIDetector().predict(file_path)
