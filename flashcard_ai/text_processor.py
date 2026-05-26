import re


def process_text(text, format_type='plain'):
    """
    Process and clean input text before sending to the AI.
    Handles plain text, markdown, and HTML formats.
    """
    if not text:
        return ''

    if format_type == 'html':
        text = _strip_html(text)
    elif format_type == 'markdown':
        text = _clean_markdown(text)

    text = _normalize_whitespace(text)
    text = _remove_special_chars(text)
    return text.strip()


def _strip_html(text):
    """Remove HTML tags from text."""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


def _clean_markdown(text):
    """Remove markdown formatting symbols."""
    text = re.sub(r'#{1,6}\s', '', text)        # headers
    text = re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', text)  # bold/italic
    text = re.sub(r'`{1,3}.*?`{1,3}', '', text, flags=re.DOTALL)  # code
    text = re.sub(r'\[.*?\]\(.*?\)', '', text)   # links
    return text


def _normalize_whitespace(text):
    """Normalize whitespace: collapse multiple spaces/newlines."""
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text


def _remove_special_chars(text):
    """Remove non-printable or problematic characters."""
    return re.sub(r'[^\x20-\x7E\n]', '', text)
