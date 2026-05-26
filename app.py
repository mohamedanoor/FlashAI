from dotenv import load_dotenv
load_dotenv()
import os
import sys
import gc
import hashlib
import secrets
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import (Flask, render_template, request, jsonify, redirect,
                   url_for, flash, send_file, make_response)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from werkzeug.security import generate_password_hash, check_password_hash
import json

from config import Config
from models import db, User, Deck, StudySession
from flashcard_ai.text_processor import process_text
from flashcard_ai.flashcard_generator import generate_flashcards
from flashcard_ai.topic_generator import generate_topic_flashcards
from flashcard_ai.file_processor import process_files

# ── App setup ──────────────────────────────────
app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
cache = Cache(app)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


with app.app_context():
    db.create_all()


# ── Utilities ──────────────────────────────────
def generate_share_code():
    return secrets.token_urlsafe(12)


# ── Error handlers ─────────────────────────────
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Rate limit exceeded. Please try again later.', 'retry_after': e.description}), 429


# ── Auth routes ────────────────────────────────
@app.route('/signup', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not username or len(username) < 3:
            flash('Username must be at least 3 characters long')
            return redirect(url_for('signup'))
        if not email or '@' not in email:
            flash('Please provide a valid email address')
            return redirect(url_for('signup'))
        if not password or len(password) < 6:
            flash('Password must be at least 6 characters long')
            return redirect(url_for('signup'))
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('signup'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('signup'))

        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        flash('Account created successfully!')
        return redirect(url_for('index'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Logged in successfully!')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!')
    return redirect(url_for('login'))


# ── Main routes ────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
@limiter.limit("20 per hour")
def generate():
    try:
        text_input = request.form.get('text_input', '').strip()
        format_type = request.form.get('format', 'plain')
        difficulty = request.form.get('difficulty', 'medium')
        extract_definitions = request.form.get('extract_definitions') == 'true'
        create_cloze = request.form.get('create_cloze') == 'true'
        question_answer = request.form.get('question_answer', 'true') == 'true'
        model = request.form.get('model', 'claude-sonnet-4-5')

        if not text_input:
            return jsonify({'error': 'No text provided'}), 400
        if len(text_input) < 50:
            return jsonify({'error': 'Please provide at least 50 characters of text'}), 400
        if len(text_input) > 10000:
            text_input = text_input[:10000]

        cache_key = hashlib.md5(f"{text_input}{difficulty}{model}".encode()).hexdigest()
        cached = cache.get(cache_key)
        if cached:
            return jsonify(cached)

        processed_text = process_text(text_input, format_type)
        flashcards = generate_flashcards(
            processed_text,
            difficulty=difficulty,
            extract_definitions=extract_definitions,
            create_cloze=create_cloze,
            question_answer=question_answer,
            model=model
        )

        response_data = {
            'flashcards': flashcards,
            'main': flashcards.get('main', []),
            'definitions': flashcards.get('definitions', []),
            'cloze': flashcards.get('cloze', []),
        }
        cache.set(cache_key, response_data, timeout=3600)
        gc.collect()
        return jsonify(response_data)

    except Exception as e:
        print(f"Error in generate route: {e}")
        gc.collect()
        return jsonify({'error': f'Error generating flashcards: {str(e)}'}), 500


@app.route('/generate_from_topic', methods=['POST'])
@limiter.limit("20 per hour")
def generate_from_topic():
    try:
        topic_input = request.form.get('topic_input', '').strip()
        difficulty = request.form.get('difficulty', 'medium')
        include_definitions = request.form.get('include_definitions') == 'true'
        include_facts = request.form.get('include_facts') == 'true'
        include_dates = request.form.get('include_dates') == 'true'
        model = request.form.get('model', 'claude-sonnet-4-5')

        if not topic_input or len(topic_input) < 3:
            return jsonify({'error': 'Topic must be at least 3 characters'}), 400

        cache_key = hashlib.md5(f"{topic_input}{difficulty}{model}".encode()).hexdigest()
        cached = cache.get(cache_key)
        if cached:
            return jsonify(cached)

        flashcards = generate_topic_flashcards(
            topic_input,
            difficulty=difficulty,
            include_definitions=include_definitions,
            include_facts=include_facts,
            include_dates=include_dates,
            model=model
        )

        response_data = {
            'flashcards': flashcards,
            'main': flashcards.get('main', []),
            'definitions': flashcards.get('definitions', []),
            'cloze': flashcards.get('cloze', []),
        }
        cache.set(cache_key, response_data, timeout=3600)
        gc.collect()
        return jsonify(response_data)

    except Exception as e:
        print(f"Error in topic generation: {e}")
        gc.collect()
        return jsonify({'error': f'Error generating flashcards: {str(e)}'}), 500


@app.route('/generate_from_files', methods=['POST'])
@limiter.limit("10 per hour")
def generate_from_files():
    try:
        files = request.files.getlist('files')
        difficulty = request.form.get('difficulty', 'medium')
        extract_all = request.form.get('extract_all') == 'true'
        use_ocr = request.form.get('use_ocr') == 'true'
        model = request.form.get('model', 'claude-sonnet-4-5')

        if not files:
            return jsonify({'error': 'No files provided'}), 400

        flashcards = process_files(
            files,
            difficulty=difficulty,
            extract_all=extract_all,
            use_ocr=use_ocr,
            model=model
        )

        response_data = {
            'flashcards': flashcards,
            'main': flashcards.get('main', []),
            'definitions': flashcards.get('definitions', []),
            'cloze': flashcards.get('cloze', []),
        }
        gc.collect()
        return jsonify(response_data)

    except Exception as e:
        print(f"Error in file processing: {e}")
        gc.collect()
        return jsonify({'error': f'Error generating flashcards: {str(e)}'}), 500


@app.route('/flashcards')
def flashcards():
    return render_template('flashcards.html')


# ── Deck management ────────────────────────────
@app.route('/save_deck', methods=['POST'])
@login_required
@limiter.limit("30 per hour")
def save_deck():
    try:
        data = request.json
        title = data.get('title', '').strip()
        cards = data.get('cards')
        description = data.get('description', '')
        source_type = data.get('source_type', 'text')
        model_used = data.get('model_used', 'claude-sonnet-4-5')

        if not title:
            return jsonify({'error': 'Deck title is required'}), 400
        if not cards:
            return jsonify({'error': 'No cards provided'}), 400

        deck = Deck(
            title=title,
            description=description,
            user_id=current_user.id,
            source_type=source_type,
            model_used=model_used
        )
        deck.set_cards(cards)
        db.session.add(deck)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Deck saved successfully', 'deck_id': deck.id})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/my_decks')
@login_required
def my_decks():
    search_query = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'recent')

    query = Deck.query.filter_by(user_id=current_user.id)
    if search_query:
        query = query.filter(Deck.title.ilike(f'%{search_query}%'))
    if sort_by == 'title':
        query = query.order_by(Deck.title)
    elif sort_by == 'cards':
        query = query.order_by(Deck.total_cards.desc())
    else:
        query = query.order_by(Deck.updated_at.desc())

    decks = query.all()
    total_decks = len(decks)
    total_cards = sum(d.total_cards for d in decks)
    recent_sessions = StudySession.query.filter_by(user_id=current_user.id)\
        .order_by(StudySession.started_at.desc()).limit(5).all()

    return render_template('my_decks.html',
                           decks=decks,
                           total_decks=total_decks,
                           total_cards=total_cards,
                           recent_sessions=recent_sessions,
                           search_query=search_query,
                           sort_by=sort_by)


@app.route('/deck/<int:deck_id>')
@login_required
def view_deck(deck_id):
    deck = Deck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id and not deck.is_public:
        flash('You do not have permission to view this deck')
        return redirect(url_for('my_decks'))

    sessions = StudySession.query.filter_by(deck_id=deck_id, user_id=current_user.id).all()
    total_sessions = len(sessions)
    total_cards_studied = sum(s.cards_studied for s in sessions)
    average_accuracy = sum(s.calculate_accuracy() for s in sessions) / total_sessions if total_sessions > 0 else 0

    return render_template('view_deck.html',
                           deck=deck,
                           total_sessions=total_sessions,
                           total_cards_studied=total_cards_studied,
                           average_accuracy=round(average_accuracy, 2))


@app.route('/load_deck/<int:deck_id>')
@login_required
def load_deck(deck_id):
    deck = Deck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id and not deck.is_public:
        flash('You do not have permission to access this deck')
        return redirect(url_for('my_decks'))

    deck.last_studied = datetime.utcnow()
    session = StudySession(user_id=current_user.id, deck_id=deck_id)
    db.session.add(session)
    db.session.commit()

    return render_template('flashcards.html', deck=deck, session_id=session.id)


@app.route('/update_study_session', methods=['POST'])
@login_required
def update_study_session():
    try:
        data = request.json
        session = StudySession.query.get_or_404(data.get('session_id'))
        if session.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403

        session.cards_studied = data.get('cards_studied', 0)
        session.cards_correct = data.get('cards_correct', 0)
        session.duration_minutes = data.get('duration_minutes', 0)
        session.study_mode = data.get('study_mode', 'flashcard')
        session.ended_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/delete_deck/<int:deck_id>', methods=['POST'])
@login_required
def delete_deck(deck_id):
    deck = Deck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id:
        flash('You do not have permission to delete this deck')
        return redirect(url_for('my_decks'))

    db.session.delete(deck)
    db.session.commit()
    flash('Deck deleted successfully')
    return redirect(url_for('my_decks'))


@app.route('/share_deck/<int:deck_id>', methods=['POST'])
@login_required
def share_deck(deck_id):
    deck = Deck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    if not deck.share_code:
        deck.share_code = generate_share_code()
        deck.is_public = True
        db.session.commit()

    share_url = url_for('shared_deck', share_code=deck.share_code, _external=True)
    return jsonify({'success': True, 'share_url': share_url, 'share_code': deck.share_code})


@app.route('/shared/<share_code>')
def shared_deck(share_code):
    deck = Deck.query.filter_by(share_code=share_code, is_public=True).first_or_404()
    return render_template('shared_deck.html', deck=deck)


@app.route('/download_deck/<int:deck_id>')
@login_required
def download_deck(deck_id):
    try:
        deck = Deck.query.get_or_404(deck_id)
        if deck.user_id != current_user.id:
            flash('You do not have permission to download this deck')
            return redirect(url_for('my_decks'))

        cards = deck.get_cards()
        html_content = render_template('pdf_template.html',
                                       title=deck.title,
                                       created=deck.created_at.isoformat(),
                                       cards=cards)
        try:
            from flask_weasyprint import HTML
            pdf = HTML(string=html_content).write_pdf()
            filename = f"{deck.title.replace(' ', '_')}.pdf"
            response = make_response(pdf)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except ImportError:
            response = make_response(html_content)
            response.headers['Content-Type'] = 'text/html'
            return response

    except Exception as e:
        flash(f"Error downloading deck: {str(e)}")
        return redirect(url_for('my_decks'))


@app.route('/export_anki/<int:deck_id>')
@login_required
def export_anki(deck_id):
    try:
        deck = Deck.query.get_or_404(deck_id)
        if deck.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403

        cards = deck.get_cards()
        anki_lines = []

        for card in cards.get('main', []):
            anki_lines.append(f"{card.get('question','')}\t{card.get('answer','')}")
        for card in cards.get('definitions', []):
            anki_lines.append(f"{card.get('question','')}\t{card.get('answer','')}")
        for card in cards.get('cloze', []):
            q = card.get('question', '')
            a = card.get('answer', '')
            cloze = q.replace('_____', f'{{{{c1::{a}}}}}')
            anki_lines.append(cloze)

        content = '\n'.join(anki_lines)
        filename = f"{deck.title.replace(' ', '_')}_anki.txt"
        response = make_response(content)
        response.headers['Content-Type'] = 'text/plain'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/analytics')
@login_required
def analytics():
    days = int(request.args.get('days', 30))
    start_date = datetime.utcnow() - timedelta(days=days)

    sessions = StudySession.query.filter(
        StudySession.user_id == current_user.id,
        StudySession.started_at >= start_date
    ).all()

    total_sessions = len(sessions)
    total_cards_studied = sum(s.cards_studied for s in sessions)
    total_time = sum(s.duration_minutes for s in sessions)
    average_accuracy = sum(s.calculate_accuracy() for s in sessions) / total_sessions if total_sessions > 0 else 0

    session_dates = {}
    for s in sessions:
        key = s.started_at.strftime('%Y-%m-%d')
        if key not in session_dates:
            session_dates[key] = {'cards_studied': 0, 'accuracy': []}
        session_dates[key]['cards_studied'] += s.cards_studied
        session_dates[key]['accuracy'].append(s.calculate_accuracy())

    chart_labels = sorted(session_dates.keys())
    chart_cards = [session_dates[d]['cards_studied'] for d in chart_labels]
    chart_accuracy = [
        sum(session_dates[d]['accuracy']) / len(session_dates[d]['accuracy'])
        if session_dates[d]['accuracy'] else 0
        for d in chart_labels
    ]

    return render_template('analytics.html',
                           total_sessions=total_sessions,
                           total_cards_studied=total_cards_studied,
                           total_time=total_time,
                           average_accuracy=round(average_accuracy, 2),
                           chart_labels=chart_labels,
                           chart_cards=chart_cards,
                           chart_accuracy=chart_accuracy,
                           days=days)


@app.route('/download_deck_direct', methods=['POST'])
def download_deck_direct():
    try:
        if request.is_json:
            data = request.json
        elif request.form.get('data'):
            data = json.loads(request.form.get('data'))
        else:
            return jsonify({'error': 'No data provided'}), 400

        html_content = render_template('pdf_template.html',
                                       title=data.get('title', 'Flashcards'),
                                       created=datetime.utcnow().isoformat(),
                                       cards=data.get('cards', {}))
        try:
            from flask_weasyprint import HTML
            pdf = HTML(string=html_content).write_pdf()
            filename = f"{data.get('title', 'flashcards').replace(' ', '_')}.pdf"
            response = make_response(pdf)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except ImportError:
            response = make_response(html_content)
            response.headers['Content-Type'] = 'text/html'
            return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)