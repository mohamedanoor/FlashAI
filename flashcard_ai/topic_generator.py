import os
import json
import anthropic


def generate_topic_flashcards(topic, difficulty='medium', include_definitions=True,
                               include_facts=True, include_dates=False, model='claude-sonnet-4-5'):
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    prompt = _build_topic_prompt(topic, difficulty, include_definitions, include_facts, include_dates)

    message = client.messages.create(
        model=model,
        max_tokens=8096,
        system='You are an expert educator who creates comprehensive, accurate flashcards. Always respond with valid JSON only. No explanations outside the JSON.',
        messages=[{'role': 'user', 'content': prompt}]
    )

    raw = message.content[0].text.strip()
    print("RAW RESPONSE:", raw)
    return _parse_response(raw)

def _build_topic_prompt(topic, difficulty, include_definitions, include_facts, include_dates):
    extras = []
    if include_definitions:
        extras.append('key term definitions')
    if include_facts:
        extras.append('important facts and concepts')
    if include_dates:
        extras.append('key dates and events')

    extras_str = ', '.join(extras) if extras else 'general knowledge'

    return f"""
Create comprehensive flashcards about "{topic}" at {difficulty} difficulty.
Focus on: {extras_str}.

Return ONLY a JSON object:
{{
  "main": [{{"question": "...", "answer": "...", "difficulty": "easy|medium|hard"}}],
  "definitions": [{{"question": "What is [term]?", "answer": "...", "difficulty": "easy|medium|hard"}}],
  "cloze": [{{"question": "sentence with _____ blank", "answer": "missing word", "difficulty": "easy|medium|hard"}}]
}}

Generate 6-10 cards per section. Make the content accurate and educational.
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