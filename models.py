from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import json

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    api_calls_count = db.Column(db.Integer, default=0)
    total_tokens_used = db.Column(db.Integer, default=0)

    decks = db.relationship('Deck', backref='owner', lazy=True, cascade='all, delete-orphan')
    study_sessions = db.relationship('StudySession', backref='user', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username}>'

    def increment_api_usage(self, tokens):
        self.api_calls_count += 1
        self.total_tokens_used += tokens
        db.session.commit()


class Deck(db.Model):
    __tablename__ = 'decks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    cards_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_studied = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_public = db.Column(db.Boolean, default=False)
    share_code = db.Column(db.String(20), unique=True)
    total_cards = db.Column(db.Integer, default=0)
    model_used = db.Column(db.String(50), default='gpt-4')
    source_type = db.Column(db.String(50))  # 'text', 'topic', 'file'

    study_sessions = db.relationship('StudySession', backref='deck', lazy=True, cascade='all, delete-orphan')

    def set_cards(self, cards_dict):
        self.cards_json = json.dumps(cards_dict)
        total = 0
        if isinstance(cards_dict, dict):
            for key in ['main', 'definitions', 'cloze']:
                if key in cards_dict and isinstance(cards_dict[key], list):
                    total += len(cards_dict[key])
        self.total_cards = total

    def get_cards(self):
        return json.loads(self.cards_json)

    def __repr__(self):
        return f'<Deck {self.title}>'


class StudySession(db.Model):
    __tablename__ = 'study_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    deck_id = db.Column(db.Integer, db.ForeignKey('decks.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)
    cards_studied = db.Column(db.Integer, default=0)
    cards_correct = db.Column(db.Integer, default=0)
    duration_minutes = db.Column(db.Integer, default=0)
    study_mode = db.Column(db.String(50))  # 'flashcard', 'quiz', 'written'

    def calculate_accuracy(self):
        if self.cards_studied == 0:
            return 0
        return round((self.cards_correct / self.cards_studied) * 100, 2)

    def __repr__(self):
        return f'<StudySession {self.id}>'


class APIUsageLog(db.Model):
    __tablename__ = 'api_usage_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    model = db.Column(db.String(50))
    tokens_used = db.Column(db.Integer)
    estimated_cost = db.Column(db.Float)
    operation_type = db.Column(db.String(50))  # 'generate', 'topic', 'file'
    success = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text)

    def __repr__(self):
        return f'<APIUsageLog {self.id}>'
