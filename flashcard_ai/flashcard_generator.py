import os
import json
import anthropic


def generate_flashcards(text, difficulty='medium', extract_definitions=True,
                        create_cloze=True, question_answer=True, model='claude-sonnet-4-5'):
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    prompt = _build_prompt(text, difficulty, extract_definitions, create_cloze, question_answer)

    message = client.messages.create(
        model=model,
        max_tokens=8096,
        system='You are an expert educator who creates high-quality flashcards. Always respond with valid JSON only. No explanations outside the JSON.',
        messages=[{'role': 'user', 'content': prompt}]
    )

    raw = message.content[0].text.strip()
    
    return _parse_response(raw)


def _build_prompt(text, difficulty, extract_definitions, create_cloze, question_answer):
    card_types = []
    if question_answer:
        card_types.append('"main": array of {"question": ..., "answer": ..., "difficulty": "easy|medium|hard"}')
    if extract_definitions:
        card_types.append('"definitions": array of {"question": "What is [term]?", "answer": ..., "difficulty": "easy|medium|hard"}')
    if create_cloze:
        card_types.append('"cloze": array of {"question": "sentence with _____ blank", "answer": "missing word/phrase", "difficulty": "easy|medium|hard"}')

    structure = ', '.join(card_types) if card_types else '"main": []'

    return f"""
Create flashcards at {difficulty} difficulty from the following text.
Return ONLY a JSON object with this structure: {{ {structure} }}
Generate 5-10 cards per enabled type. Make questions clear and answers concise.

TEXT:
{text}
"""


def _parse_response(raw):
    try:
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        return {'main': [], 'definitions': [], 'cloze': [], 'error': 'Failed to parse AI response'}