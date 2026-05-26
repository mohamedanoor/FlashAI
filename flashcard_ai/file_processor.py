import os
import json
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'doc'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def process_files(files, difficulty='medium', extract_all=False, use_ocr=False, model='gpt-4'):
    """
    Extract text from uploaded files and generate flashcards.
    Supports .txt, .pdf, .docx files.
    """
    combined_text = ''

    for file in files:
        if not file or not file.filename:
            continue
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

        try:
            if ext == 'txt':
                combined_text += file.read().decode('utf-8', errors='ignore') + '\n\n'
            elif ext == 'pdf':
                combined_text += _extract_pdf(file) + '\n\n'
            elif ext in ('docx', 'doc'):
                combined_text += _extract_docx(file) + '\n\n'
        except Exception as e:
            print(f'Error processing file {filename}: {e}')
            continue

    if not combined_text.strip():
        return {'main': [], 'definitions': [], 'cloze': [], 'error': 'No readable text found in uploaded files'}

    # Trim to avoid token overflow
    combined_text = combined_text[:8000]

    return _generate_from_text(combined_text, difficulty, model)


def _extract_pdf(file):
    """Extract text from a PDF file using pdfminer."""
    try:
        from pdfminer.high_level import extract_text_to_fp
        from pdfminer.layout import LAParams
        import io

        output = io.StringIO()
        file.seek(0)
        extract_text_to_fp(file, output, laparams=LAParams())
        return output.getvalue()
    except Exception as e:
        print(f'PDF extraction error: {e}')
        return ''


def _extract_docx(file):
    """Extract text from a Word document."""
    try:
        import docx
        import io

        file.seek(0)
        doc = docx.Document(io.BytesIO(file.read()))
        return '\n'.join(para.text for para in doc.paragraphs if para.text.strip())
    except Exception as e:
        print(f'DOCX extraction error: {e}')
        return ''


def _generate_from_text(text, difficulty, model):
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

    prompt = f"""
Create flashcards at {difficulty} difficulty from the following document content.
Return ONLY a JSON object:
{{
  "main": [{{"question": "...", "answer": "...", "difficulty": "easy|medium|hard"}}],
  "definitions": [{{"question": "What is [term]?", "answer": "...", "difficulty": "easy|medium|hard"}}],
  "cloze": [{{"question": "sentence with _____ blank", "answer": "missing word", "difficulty": "easy|medium|hard"}}]
}}
Generate 5-10 cards per section.

DOCUMENT:
{text}
"""
    try:
        message = client.messages.create(
            model=model,
            max_tokens=8096,
            system='You are an expert educator. Return valid JSON only.',
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = message.content[0].text.strip()
        print("FILE RAW RESPONSE:", raw)  
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        return {'main': [], 'definitions': [], 'cloze': [], 'error': str(e)}