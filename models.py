"""SQLAlchemy database models following the CDC V3 schema."""
import uuid
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def generate_uuid():
    return str(uuid.uuid4())


class Class(db.Model):
    __tablename__ = 'classes'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(100), nullable=False)
    level = db.Column(db.String(50), nullable=False)  # College, Qualifiant
    users = db.relationship('User', backref='school_class', lazy=True)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # ELEVE, ENSEIGNANT, ADMIN
    full_name = db.Column(db.String(150), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.id'), nullable=True)
    language_pref = db.Column(db.String(5), default='fr')
    notifications_enabled = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    conversations = db.relationship('Conversation', backref='user', lazy=True)
    alerts = db.relationship('Alert', backref='student', lazy=True, foreign_keys='Alert.student_id')

    def to_dict(self, include_sensitive=False):
        data = {
            'id': self.id,
            'email': self.email,
            'role': self.role,
            'full_name': self.full_name,
            'class_id': self.class_id,
            'class_name': self.school_class.name if self.school_class else None,
            'language_pref': self.language_pref,
            'notifications_enabled': self.notifications_enabled,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }
        return data


class Conversation(db.Model):
    __tablename__ = 'conversations'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    emotion_initial = db.Column(db.String(30), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    messages = db.relationship('Message', backref='conversation', lazy=True,
                               order_by='Message.timestamp')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'started_at': self.started_at.isoformat(),
            'emotion_initial': self.emotion_initial,
            'is_active': self.is_active,
            'message_count': len(self.messages) if self.messages else 0,
        }


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    conversation_id = db.Column(db.String(36), db.ForeignKey('conversations.id'), nullable=False)
    sender = db.Column(db.String(10), nullable=False)  # ELEVE or CHATBOT
    content_encrypted = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    flagged = db.Column(db.Boolean, default=False)
    language_detected = db.Column(db.String(20), nullable=True)
    sentiment_label = db.Column(db.String(20), nullable=True)
    emotion_label = db.Column(db.String(20), nullable=True)
    analysis_confidence = db.Column(db.Float, nullable=True)
    topic_keywords = db.Column(db.String(200), nullable=True)

    def to_dict(self, decrypted_content=None, include_analysis=False):
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'sender': self.sender,
            'content': decrypted_content or '',
            'timestamp': self.timestamp.isoformat(),
            'flagged': self.flagged,
            **({
                'language_detected': self.language_detected,
                'sentiment_label': self.sentiment_label,
                'emotion_label': self.emotion_label,
                'analysis_confidence': self.analysis_confidence,
                'topic_keywords': self.topic_keywords,
            } if include_analysis else {})
        }


class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='password_reset_tokens')


class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.String(500), nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class Alert(db.Model):
    __tablename__ = 'alerts'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    student_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    conversation_id = db.Column(db.String(36), db.ForeignKey('conversations.id'), nullable=True)
    severity = db.Column(db.String(20), nullable=False)  # CRITIQUE, ELEVEE, MODEREE
    detected_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    alert_excerpt = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='NOUVELLE')  # NOUVELLE, EN_TRAITEMENT, RESOLUE
    notified_user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    resolution_note = db.Column(db.Text, nullable=True)

    notified_user = db.relationship('User', foreign_keys=[notified_user_id])
    conversation = db.relationship('Conversation')

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student.full_name if self.student else None,
            'student_class': self.student.school_class.name if self.student and self.student.school_class else None,
            'severity': self.severity,
            'detected_at': self.detected_at.isoformat(),
            'alert_excerpt': self.alert_excerpt,
            'status': self.status,
            'notified_user_id': self.notified_user_id,
            'resolution_note': self.resolution_note,
        }
