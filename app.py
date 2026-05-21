"""Main Flask application - Chatbot Socio-Emotionnel."""
import io
import os
import logging
import hashlib
from logging.handlers import RotatingFileHandler
import secrets
from collections import Counter
from datetime import datetime, timedelta, timezone

from flask import (Flask, render_template, request, jsonify, g,
                   redirect, url_for, make_response, send_file)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_cors import CORS

from config import Config
from models import db, User, Conversation, Message, Alert, Class, PasswordResetToken, SystemSetting
from auth import (hash_password, verify_password, generate_token,
                  decode_token, login_required, role_required)
from chat_service import ChatService
from alerts import AlertService
from encryption import encrypt_message, decrypt_message

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config.from_object(Config)

if Config.ALLOWED_ORIGINS:
    origins = [o.strip() for o in Config.ALLOWED_ORIGINS.split(',') if o.strip()]
    if origins:
        CORS(app, origins=origins, supports_credentials=True)

db.init_app(app)
migrate = Migrate(app, db)
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per hour"],
                  storage_uri="memory://")

chat_service = ChatService()

# Logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.DEBUG),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

log_dir = os.path.join(app.instance_path, 'logs')
try:
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=1_000_000,
        backupCount=3,
    )
    file_handler.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))
    logger.addHandler(file_handler)
except Exception as e:
    logger.warning("Unable to initialize file logging: %s", str(e))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
EMOTION_SCORES = {
    'serein': 8,
    'bien': 7,
    'stresse': 4,
    'anxieux': 3,
    'triste': 2,
    'en_colere': 2,
    'fatigue': 3,
    'confus': 4,
    'neutre': 5,
}
SENTIMENT_SCORES = {
    'positive': 8,
    'neutral': 5,
    'negative': 3,
    'critical': 1,
}


def get_setting(key: str, default=None):
    setting = db.session.get(SystemSetting, key)
    if setting and setting.value is not None:
        return setting.value
    return default


def set_setting(key: str, value: str):
    now = datetime.now(timezone.utc)
    setting = db.session.get(SystemSetting, key)
    if setting:
        setting.value = value
        setting.updated_at = now
    else:
        setting = SystemSetting(key=key, value=value, updated_at=now)
        db.session.add(setting)
    db.session.commit()


def _generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _set_csrf_cookie(response):
    token = _generate_csrf_token()
    response.set_cookie(
        'csrf_token',
        token,
        httponly=False,
        samesite='Strict',
        max_age=Config.JWT_EXPIRY_HOURS * 3600,
    )
    return response


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _build_reset_link(token: str) -> str:
    base_url = Config.APP_BASE_URL.strip() if Config.APP_BASE_URL else ''
    if not base_url:
        base_url = request.host_url.rstrip('/')
    return f"{base_url}/reset?token={token}"


def _build_wordcloud_from_messages(messages: list[Message]) -> list[list]:
    counter = Counter()
    for msg in messages:
        if not msg.topic_keywords:
            continue
        for kw in msg.topic_keywords.split(','):
            key = kw.strip().lower()
            if not key:
                continue
            counter[key] += 1
    return [[k, v] for k, v in counter.most_common(30)]


def _send_email(subject: str, body: str, recipients: list[str]) -> bool:
    if not Config.SMTP_SERVER or not Config.SMTP_USER:
        logger.warning("SMTP not configured, skipping email")
        return False
    if not recipients:
        return False

    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import smtplib

    msg = MIMEMultipart()
    msg['From'] = Config.SMTP_USER
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
            server.starttls()
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error("SMTP error: %s", str(e))
        return False


def _cleanup_old_data(retention_days: int) -> dict:
    if retention_days <= 0:
        return {'deleted_conversations': 0, 'deleted_messages': 0}

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    alert_conv_ids = {
        cid for (cid,) in db.session.query(Alert.conversation_id)
        .filter(Alert.conversation_id.isnot(None)).all()
    }

    deleted_messages = 0
    deleted_conversations = 0
    old_convs = Conversation.query.filter(Conversation.started_at < cutoff).all()
    for conv in old_convs:
        if conv.id in alert_conv_ids:
            continue
        deleted_messages += Message.query.filter_by(conversation_id=conv.id).delete()
        db.session.delete(conv)
        deleted_conversations += 1

    db.session.commit()
    return {
        'deleted_conversations': deleted_conversations,
        'deleted_messages': deleted_messages,
    }


def _calculate_student_wellbeing(student_id: str) -> tuple[float, str]:
    now = datetime.now(timezone.utc)
    recent_msgs = Message.query.join(Conversation).filter(
        Conversation.user_id == student_id,
        Message.sender == 'ELEVE',
        Message.timestamp >= now - timedelta(days=14),
    ).order_by(Message.timestamp.desc()).limit(20).all()

    scores = []
    for msg in recent_msgs:
        if msg.emotion_label in EMOTION_SCORES:
            scores.append(EMOTION_SCORES[msg.emotion_label])
        elif msg.sentiment_label in SENTIMENT_SCORES:
            scores.append(SENTIMENT_SCORES[msg.sentiment_label])

    if not scores:
        last_conv = Conversation.query.filter(
            Conversation.user_id == student_id,
            Conversation.emotion_initial.isnot(None),
        ).order_by(Conversation.started_at.desc()).first()
        if last_conv and last_conv.emotion_initial in EMOTION_SCORES:
            scores.append(EMOTION_SCORES[last_conv.emotion_initial])

    if not scores:
        return 5.0, 'neutre'

    avg = round(sum(scores) / len(scores), 1)
    if avg >= 6:
        return avg, 'ok'
    if avg >= 4:
        return avg, 'watch'
    return avg, 'alert'

# ---------------------------------------------------------------------------
# Before-request: load user from JWT cookie
# ---------------------------------------------------------------------------
@app.before_request
def load_user():
    g.current_user = None
    token = request.cookies.get('auth_token')
    if token:
        payload = decode_token(token)
        if payload:
            user = db.session.get(User, payload.get('user_id'))
            if user and user.is_active:
                g.current_user = user


@app.before_request
def csrf_protect():
    if request.method not in ('POST', 'PUT', 'DELETE'):
        return None
    if not request.path.startswith('/api/'):
        return None
    if app.config.get('TESTING'):
        return None

    exempt = {
        'api_login',
        'api_password_reset_request',
        'api_password_reset',
    }
    if request.endpoint in exempt:
        return None

    header_token = request.headers.get('X-CSRF-Token')
    cookie_token = request.cookies.get('csrf_token')
    if not header_token or not cookie_token or header_token != cookie_token:
        return jsonify({'error': 'CSRF token manquant ou invalide'}), 403
    return None


# ---------------------------------------------------------------------------
# PAGE ROUTES (serve HTML templates)
# ---------------------------------------------------------------------------
@app.route('/')
def login_page():
    if g.current_user:
        return _redirect_by_role(g.current_user.role)
    return render_template('login.html')


@app.route('/chat')
@login_required
@role_required('ELEVE')
def chat_page():
    return render_template('chat.html', user=g.current_user)


@app.route('/dashboard')
@login_required
@role_required('ELEVE')
def dashboard_eleve_page():
    return render_template('dashboard_eleve.html', user=g.current_user)


@app.route('/teacher')
@login_required
@role_required('ENSEIGNANT')
def teacher_page():
    return render_template('dashboard_enseignant.html', user=g.current_user)


@app.route('/admin')
@login_required
@role_required('ADMIN')
def admin_page():
    return render_template('admin.html', user=g.current_user)


@app.route('/privacy')
def privacy_page():
    return render_template('privacy.html')


@app.route('/reset')
def reset_password_page():
    token = request.args.get('token', '').strip()
    return render_template('reset_password.html', token=token)


def _redirect_by_role(role):
    if role == 'ELEVE':
        return redirect(url_for('chat_page'))
    elif role == 'ENSEIGNANT':
        return redirect(url_for('teacher_page'))
    elif role == 'ADMIN':
        return redirect(url_for('admin_page'))
    return redirect(url_for('login_page'))


# ---------------------------------------------------------------------------
# AUTH API
# ---------------------------------------------------------------------------
@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("10/minute")
def api_login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Donnees manquantes'}), 400

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email et mot de passe requis'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.is_active:
        return jsonify({'error': 'Identifiants invalides'}), 401

    # Check account lockout
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        remaining = (user.locked_until - datetime.now(timezone.utc)).seconds // 60
        return jsonify({'error': f'Compte verrouille. Reessayez dans {remaining} minutes.'}), 423

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= Config.MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=Config.LOCKOUT_DURATION_MINUTES)
            user.failed_login_attempts = 0
            db.session.commit()
            return jsonify({'error': 'Trop de tentatives. Compte verrouille temporairement.'}), 423
        db.session.commit()
        return jsonify({'error': 'Identifiants invalides'}), 401

    # Success
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.now(timezone.utc)
    db.session.commit()

    token = generate_token(user.id, user.role)
    resp = make_response(jsonify({
        'message': 'Connexion reussie',
        'user': user.to_dict(),
    }))
    resp.set_cookie('auth_token', token, httponly=True, samesite='Strict',
                    max_age=Config.JWT_EXPIRY_HOURS * 3600)
    return _set_csrf_cookie(resp)


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    resp = make_response(jsonify({'message': 'Deconnexion reussie'}))
    resp.delete_cookie('auth_token')
    resp.delete_cookie('csrf_token')
    return resp


@app.route('/api/auth/forgot', methods=['POST'])
@limiter.limit("5/minute")
def api_password_reset_request():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    if not email:
        return jsonify({'error': 'Email requis'}), 400

    user = User.query.filter_by(email=email, is_active=True).first()
    if user:
        token = secrets.token_urlsafe(32)
        token_hash = _hash_token(token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        reset = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.session.add(reset)
        db.session.commit()

        reset_link = _build_reset_link(token)
        body = (
            "Vous avez demande une reinitialisation de mot de passe.\n\n"
            f"Lien de reinitialisation (valide 1 heure):\n{reset_link}\n\n"
            "Si vous n'etes pas a l'origine de cette demande, ignorez ce message."
        )
        _send_email("Reinitialisation de mot de passe", body, [user.email])

    return jsonify({'message': 'Si un compte existe, un email a ete envoye.'})


@app.route('/api/auth/reset', methods=['POST'])
@limiter.limit("10/minute")
def api_password_reset():
    data = request.get_json() or {}
    token = data.get('token', '').strip()
    new_password = data.get('password', '')

    if not token or not new_password or len(new_password) < 8:
        return jsonify({'error': 'Token ou mot de passe invalide'}), 400

    token_hash = _hash_token(token)
    reset = PasswordResetToken.query.filter_by(
        token_hash=token_hash, used=False
    ).order_by(PasswordResetToken.created_at.desc()).first()

    if not reset or reset.expires_at < datetime.now(timezone.utc):
        return jsonify({'error': 'Lien invalide ou expire'}), 400

    user = db.session.get(User, reset.user_id)
    if not user or not user.is_active:
        return jsonify({'error': 'Utilisateur introuvable'}), 404

    user.password_hash = hash_password(new_password)
    reset.used = True
    db.session.commit()
    return jsonify({'message': 'Mot de passe mis a jour'})


@app.route('/api/auth/me')
@login_required
def api_me():
    return jsonify({'user': g.current_user.to_dict()})


# ---------------------------------------------------------------------------
# CHAT API
# ---------------------------------------------------------------------------
@app.route('/api/chat/send', methods=['POST'])
@login_required
@role_required('ELEVE')
@limiter.limit(f"{Config.MAX_MESSAGES_PER_HOUR}/hour")
def api_send_message():
    data = request.get_json()
    if not data or not data.get('message', '').strip():
        return jsonify({'error': 'Message vide'}), 400

    user_message = data['message'].strip()
    conversation_id = data.get('conversation_id')

    # Get or create conversation
    if conversation_id:
        conv = Conversation.query.filter_by(
            id=conversation_id, user_id=g.current_user.id
        ).first()
        if not conv:
            return jsonify({'error': 'Conversation introuvable'}), 404
    else:
        conv = Conversation.query.filter_by(
            user_id=g.current_user.id, is_active=True
        ).order_by(Conversation.started_at.desc()).first()
        if not conv:
            conv = Conversation(user_id=g.current_user.id)
            db.session.add(conv)
            db.session.commit()

    # Count today's messages for rate display
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = Message.query.join(Conversation).filter(
        Conversation.user_id == g.current_user.id,
        Message.sender == 'ELEVE',
        Message.timestamp >= today_start
    ).count()

    # Build history from existing messages
    history = []
    for msg in conv.messages:
        try:
            content = decrypt_message(msg.content_encrypted, Config.ENCRYPTION_KEY)
        except Exception:
            content = ''
        history.append({'sender': msg.sender, 'content': content})

    # Get response from Gemini
    bot_response_raw = chat_service.get_response(user_message, history)

    # Sentiment/language analysis for analytics
    analysis = chat_service.analyze_message(user_message, history)
    language_detected = (analysis.get('language') or '').strip() or None
    sentiment_label = (analysis.get('sentiment') or '').strip() or None
    emotion_label = (analysis.get('emotion') or '').strip() or None
    confidence_val = analysis.get('confidence')
    try:
        analysis_confidence = float(confidence_val) if confidence_val is not None else None
    except (TypeError, ValueError):
        analysis_confidence = None

    topics = analysis.get('topics')
    if isinstance(topics, list):
        topic_keywords = ', '.join([str(t).strip() for t in topics if str(t).strip()])
    else:
        topic_keywords = (str(topics).strip() if topics else None)

    # Dual alert detection
    alert = AlertService.process_dual_detection(
        student_message=user_message,
        bot_response=bot_response_raw,
        student_id=g.current_user.id,
        conversation_id=conv.id,
    )

    # Clean response (remove alert tag if present)
    bot_response = ChatService.clean_response(bot_response_raw)

    # Encrypt and store messages
    user_msg = Message(
        conversation_id=conv.id,
        sender='ELEVE',
        content_encrypted=encrypt_message(user_message, Config.ENCRYPTION_KEY),
        flagged=alert is not None,
        language_detected=language_detected,
        sentiment_label=sentiment_label,
        emotion_label=emotion_label,
        analysis_confidence=analysis_confidence,
        topic_keywords=topic_keywords,
    )
    bot_msg = Message(
        conversation_id=conv.id,
        sender='CHATBOT',
        content_encrypted=encrypt_message(bot_response, Config.ENCRYPTION_KEY),
    )
    db.session.add(user_msg)
    db.session.add(bot_msg)
    db.session.commit()

    return jsonify({
        'response': bot_response,
        'conversation_id': conv.id,
        'message_count_today': today_count + 1,
        'alert_triggered': alert is not None,
        'timestamp': bot_msg.timestamp.isoformat(),
    })


@app.route('/api/chat/conversations')
@login_required
@role_required('ELEVE')
def api_conversations():
    convs = Conversation.query.filter_by(
        user_id=g.current_user.id
    ).order_by(Conversation.started_at.desc()).limit(50).all()
    return jsonify({'conversations': [c.to_dict() for c in convs]})


@app.route('/api/chat/conversations/<conv_id>/messages')
@login_required
@role_required('ELEVE')
def api_conversation_messages(conv_id):
    conv = Conversation.query.filter_by(
        id=conv_id, user_id=g.current_user.id
    ).first()
    if not conv:
        return jsonify({'error': 'Conversation introuvable'}), 404

    messages = []
    for msg in conv.messages:
        try:
            content = decrypt_message(msg.content_encrypted, Config.ENCRYPTION_KEY)
        except Exception:
            content = '[Message indechiffrable]'
        messages.append(msg.to_dict(decrypted_content=content))

    return jsonify({'messages': messages, 'conversation': conv.to_dict()})


@app.route('/api/chat/new-session', methods=['POST'])
@login_required
@role_required('ELEVE')
def api_new_session():
    data = request.get_json() or {}
    emotion = data.get('emotion', '')

    # Deactivate previous conversations
    Conversation.query.filter_by(
        user_id=g.current_user.id, is_active=True
    ).update({'is_active': False})

    conv = Conversation(
        user_id=g.current_user.id,
        emotion_initial=emotion,
        is_active=True,
    )
    db.session.add(conv)
    db.session.commit()

    return jsonify({'conversation': conv.to_dict()})


@app.route('/api/chat/conversations/<conv_id>', methods=['DELETE'])
@login_required
@role_required('ELEVE')
def api_delete_conversation(conv_id):
    """Delete a single conversation and its messages."""
    conv = Conversation.query.filter_by(
        id=conv_id, user_id=g.current_user.id
    ).first()
    if not conv:
        return jsonify({'error': 'Conversation introuvable'}), 404

    Message.query.filter_by(conversation_id=conv.id).delete()
    db.session.delete(conv)
    db.session.commit()
    return jsonify({'message': 'Conversation supprimee'})


# ---------------------------------------------------------------------------
# ALERTS API
# ---------------------------------------------------------------------------
@app.route('/api/alerts')
@login_required
@role_required('ENSEIGNANT', 'ADMIN')
def api_alerts():
    query = Alert.query

    if g.current_user.role == 'ENSEIGNANT':
        # Only alerts for students in teacher's class
        query = query.join(User, Alert.student_id == User.id).filter(
            User.class_id == g.current_user.class_id
        )

    status_filter = request.args.get('status')
    if status_filter:
        query = query.filter(Alert.status == status_filter)

    severity_filter = request.args.get('severity')
    if severity_filter:
        query = query.filter(Alert.severity == severity_filter)

    alerts = query.order_by(
        db.case(
            (Alert.severity == 'CRITIQUE', 1),
            (Alert.severity == 'ELEVEE', 2),
            (Alert.severity == 'MODEREE', 3),
        ),
        Alert.detected_at.desc()
    ).limit(100).all()

    return jsonify({'alerts': [a.to_dict() for a in alerts]})


@app.route('/api/alerts/<alert_id>', methods=['PUT'])
@login_required
@role_required('ENSEIGNANT', 'ADMIN')
def api_update_alert(alert_id):
    alert = db.session.get(Alert, alert_id)
    if not alert:
        return jsonify({'error': 'Alerte introuvable'}), 404

    data = request.get_json()
    if data.get('status'):
        alert.status = data['status']
    if data.get('resolution_note') is not None:
        alert.resolution_note = data['resolution_note']
    if data.get('notified_user_id'):
        alert.notified_user_id = data['notified_user_id']

    db.session.commit()
    return jsonify({'alert': alert.to_dict()})


@app.route('/api/alerts/stats')
@login_required
@role_required('ENSEIGNANT', 'ADMIN')
def api_alert_stats():
    query = Alert.query
    if g.current_user.role == 'ENSEIGNANT':
        query = query.join(User, Alert.student_id == User.id).filter(
            User.class_id == g.current_user.class_id
        )

    total = query.count()
    nouvelle = query.filter(Alert.status == 'NOUVELLE').count()
    en_traitement = query.filter(Alert.status == 'EN_TRAITEMENT').count()
    resolue = query.filter(Alert.status == 'RESOLUE').count()

    critique = query.filter(Alert.severity == 'CRITIQUE').count()
    elevee = query.filter(Alert.severity == 'ELEVEE').count()
    moderee = query.filter(Alert.severity == 'MODEREE').count()

    return jsonify({
        'total': total,
        'by_status': {'NOUVELLE': nouvelle, 'EN_TRAITEMENT': en_traitement, 'RESOLUE': resolue},
        'by_severity': {'CRITIQUE': critique, 'ELEVEE': elevee, 'MODEREE': moderee},
    })


# ---------------------------------------------------------------------------
# DASHBOARD API
# ---------------------------------------------------------------------------
@app.route('/api/dashboard/student')
@login_required
@role_required('ELEVE')
def api_dashboard_student():
    user_id = g.current_user.id
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Sessions this month
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    sessions_count = Conversation.query.filter(
        Conversation.user_id == user_id,
        Conversation.started_at >= month_start,
    ).count()

    # Emotional data for last 30 days
    convs = Conversation.query.filter(
        Conversation.user_id == user_id,
        Conversation.started_at >= thirty_days_ago,
        Conversation.emotion_initial.isnot(None),
    ).order_by(Conversation.started_at).all()

    emotions_timeline = [{
        'date': c.started_at.strftime('%d/%m'),
        'emotion': c.emotion_initial,
    } for c in convs]

    # Total messages
    total_messages = Message.query.join(Conversation).filter(
        Conversation.user_id == user_id,
        Message.sender == 'ELEVE',
    ).count()

    # Word cloud topics (last 30 days)
    topic_messages = Message.query.join(Conversation).filter(
        Conversation.user_id == user_id,
        Message.sender == 'ELEVE',
        Message.timestamp >= thirty_days_ago,
    ).all()
    wordcloud = _build_wordcloud_from_messages(topic_messages)

    return jsonify({
        'sessions_this_month': sessions_count,
        'total_messages': total_messages,
        'emotions_timeline': emotions_timeline,
        'themes_wordcloud': wordcloud,
    })


@app.route('/api/dashboard/teacher')
@login_required
@role_required('ENSEIGNANT')
def api_dashboard_teacher():
    class_id = g.current_user.class_id
    if not class_id:
        return jsonify({'classes': [], 'stats': {}})

    # Students in class
    students = User.query.filter_by(class_id=class_id, role='ELEVE', is_active=True).all()
    student_ids = [s.id for s in students]

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    # Usage rate this week
    active_students = Conversation.query.filter(
        Conversation.user_id.in_(student_ids),
        Conversation.started_at >= week_ago,
    ).distinct(Conversation.user_id).count() if student_ids else 0

    # Recent emotions
    recent_emotions = {}
    for sid in student_ids:
        last_conv = Conversation.query.filter(
            Conversation.user_id == sid,
            Conversation.emotion_initial.isnot(None),
        ).order_by(Conversation.started_at.desc()).first()
        if last_conv and last_conv.emotion_initial:
            e = last_conv.emotion_initial
            recent_emotions[e] = recent_emotions.get(e, 0) + 1

    # Pending alerts
    pending_alerts = Alert.query.join(User, Alert.student_id == User.id).filter(
        User.class_id == class_id,
        Alert.status != 'RESOLUE',
    ).count()

    # Per-student wellbeing indicators
    student_wellbeing = []
    scores = []
    for student in students:
        score, status = _calculate_student_wellbeing(student.id)
        scores.append(score)
        student_wellbeing.append({
            'id': student.id,
            'name': student.full_name,
            'score': score,
            'status': status,
        })

    class_wellbeing_score = round(sum(scores) / len(scores), 1) if scores else 0

    # Themes word cloud (anonymized)
    topic_messages = Message.query.join(Conversation).filter(
        Conversation.user_id.in_(student_ids),
        Message.sender == 'ELEVE',
        Message.timestamp >= week_ago,
    ).all() if student_ids else []
    class_wordcloud = _build_wordcloud_from_messages(topic_messages)

    return jsonify({
        'class_name': g.current_user.school_class.name if g.current_user.school_class else '',
        'total_students': len(students),
        'active_this_week': active_students,
        'emotion_distribution': recent_emotions,
        'pending_alerts': pending_alerts,
        'class_wellbeing_score': class_wellbeing_score,
        'student_wellbeing': student_wellbeing,
        'themes_wordcloud': class_wordcloud,
    })


@app.route('/api/dashboard/admin')
@login_required
@role_required('ADMIN')
def api_dashboard_admin():
    total_users = User.query.filter_by(is_active=True).count()
    total_students = User.query.filter_by(role='ELEVE', is_active=True).count()
    total_teachers = User.query.filter_by(role='ENSEIGNANT', is_active=True).count()
    total_conversations = Conversation.query.count()
    total_alerts = Alert.query.count()
    pending_alerts = Alert.query.filter(Alert.status != 'RESOLUE').count()

    classes = Class.query.all()
    class_stats = []
    for c in classes:
        student_count = User.query.filter_by(class_id=c.id, role='ELEVE', is_active=True).count()
        class_stats.append({'id': c.id, 'name': c.name, 'level': c.level,
                            'student_count': student_count})

    return jsonify({
        'total_users': total_users,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_conversations': total_conversations,
        'total_alerts': total_alerts,
        'pending_alerts': pending_alerts,
        'classes': class_stats,
    })


# ---------------------------------------------------------------------------
# ADMIN SETTINGS API
# ---------------------------------------------------------------------------
@app.route('/api/admin/settings', methods=['GET', 'PUT'])
@login_required
@role_required('ADMIN')
def api_admin_settings():
    try:
        retention_days = int(get_setting('data_retention_days', Config.DATA_RETENTION_DAYS))
    except (TypeError, ValueError):
        retention_days = int(Config.DATA_RETENTION_DAYS)

    settings_payload = {
        'alert_recipient_default': get_setting('alert_recipient_default', Config.ALERT_RECIPIENT_DEFAULT) or '',
        'alert_recipient_critique': get_setting('alert_recipient_critique', Config.ALERT_RECIPIENT_CRITIQUE) or '',
        'alert_recipient_elevee': get_setting('alert_recipient_elevee', Config.ALERT_RECIPIENT_ELEVEE) or '',
        'alert_recipient_moderee': get_setting('alert_recipient_moderee', Config.ALERT_RECIPIENT_MODEREE) or '',
        'data_retention_days': retention_days,
    }

    if request.method == 'GET':
        return jsonify({'settings': settings_payload})

    data = request.get_json() or {}
    for key in settings_payload.keys():
        if key in data and data[key] is not None:
            value = str(data[key]).strip()
            set_setting(key, value)

    try:
        retention_days = int(get_setting('data_retention_days', Config.DATA_RETENTION_DAYS))
    except (TypeError, ValueError):
        retention_days = int(Config.DATA_RETENTION_DAYS)

    updated = {
        'alert_recipient_default': get_setting('alert_recipient_default', Config.ALERT_RECIPIENT_DEFAULT) or '',
        'alert_recipient_critique': get_setting('alert_recipient_critique', Config.ALERT_RECIPIENT_CRITIQUE) or '',
        'alert_recipient_elevee': get_setting('alert_recipient_elevee', Config.ALERT_RECIPIENT_ELEVEE) or '',
        'alert_recipient_moderee': get_setting('alert_recipient_moderee', Config.ALERT_RECIPIENT_MODEREE) or '',
        'data_retention_days': retention_days,
    }
    return jsonify({'settings': updated})


@app.route('/api/admin/cleanup', methods=['POST'])
@login_required
@role_required('ADMIN')
def api_admin_cleanup():
    try:
        retention_days = int(get_setting('data_retention_days', Config.DATA_RETENTION_DAYS))
    except (TypeError, ValueError):
        retention_days = int(Config.DATA_RETENTION_DAYS)
    result = _cleanup_old_data(retention_days)
    return jsonify({'result': result})


# ---------------------------------------------------------------------------
# USER MANAGEMENT API (Admin only)
# ---------------------------------------------------------------------------
@app.route('/api/users')
@login_required
@role_required('ADMIN')
def api_users():
    role_filter = request.args.get('role')
    query = User.query
    if role_filter:
        query = query.filter_by(role=role_filter)
    users = query.order_by(User.created_at.desc()).all()
    return jsonify({'users': [u.to_dict() for u in users]})


@app.route('/api/users', methods=['POST'])
@login_required
@role_required('ADMIN')
def api_create_user():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Donnees manquantes'}), 400

    required = ['email', 'password', 'role', 'full_name']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Champ requis: {field}'}), 400

    if User.query.filter_by(email=data['email'].strip().lower()).first():
        return jsonify({'error': 'Cet email est deja utilise'}), 409

    if data['role'] not in ('ELEVE', 'ENSEIGNANT', 'ADMIN'):
        return jsonify({'error': 'Role invalide'}), 400

    user = User(
        email=data['email'].strip().lower(),
        password_hash=hash_password(data['password']),
        role=data['role'],
        full_name=data['full_name'].strip(),
        class_id=data.get('class_id'),
        language_pref=data.get('language_pref', 'fr'),
        is_active=True,
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({'user': user.to_dict()}), 201


@app.route('/api/users/<user_id>', methods=['PUT'])
@login_required
@role_required('ADMIN')
def api_update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'Utilisateur introuvable'}), 404

    data = request.get_json()
    if data.get('full_name'):
        user.full_name = data['full_name']
    if data.get('email'):
        user.email = data['email'].strip().lower()
    if data.get('role') and data['role'] in ('ELEVE', 'ENSEIGNANT', 'ADMIN'):
        user.role = data['role']
    if data.get('class_id') is not None:
        user.class_id = data['class_id'] or None
    if data.get('language_pref'):
        user.language_pref = data['language_pref']
    if 'is_active' in data:
        user.is_active = data['is_active']
    if data.get('password'):
        user.password_hash = hash_password(data['password'])

    db.session.commit()
    return jsonify({'user': user.to_dict()})


@app.route('/api/users/<user_id>', methods=['DELETE'])
@login_required
@role_required('ADMIN')
def api_deactivate_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'Utilisateur introuvable'}), 404
    user.is_active = False
    db.session.commit()
    return jsonify({'message': 'Utilisateur desactive'})


# ---------------------------------------------------------------------------
# CLASS MANAGEMENT API (Admin)
# ---------------------------------------------------------------------------
@app.route('/api/classes')
@login_required
def api_classes():
    classes = Class.query.order_by(Class.name).all()
    return jsonify({'classes': [{'id': c.id, 'name': c.name, 'level': c.level} for c in classes]})


@app.route('/api/classes', methods=['POST'])
@login_required
@role_required('ADMIN')
def api_create_class():
    data = request.get_json()
    if not data or not data.get('name') or not data.get('level'):
        return jsonify({'error': 'Nom et niveau requis'}), 400
    c = Class(name=data['name'], level=data['level'])
    db.session.add(c)
    db.session.commit()
    return jsonify({'class': {'id': c.id, 'name': c.name, 'level': c.level}}), 201


# ---------------------------------------------------------------------------
# CSV EXPORT (Admin)
# ---------------------------------------------------------------------------
@app.route('/api/export/alerts')
@login_required
@role_required('ADMIN')
def api_export_alerts():
    import csv
    import io
    alerts = Alert.query.order_by(Alert.detected_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Eleve', 'Gravite', 'Date', 'Statut', 'Extrait', 'Note'])
    for a in alerts:
        writer.writerow([
            a.id, a.student.full_name if a.student else '', a.severity,
            a.detected_at.strftime('%d/%m/%Y %H:%M'), a.status,
            a.alert_excerpt, a.resolution_note or ''
        ])
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = 'attachment; filename=alertes_export.csv'
    return response


@app.route('/api/export/alerts/pdf')
@login_required
@role_required('ADMIN')
def api_export_alerts_pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    alerts = Alert.query.order_by(Alert.detected_at.desc()).all()
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Rapport des alertes")
    y -= 20

    c.setFont("Helvetica", 9)
    for alert in alerts:
        if y < 60:
            c.showPage()
            y = height - 40
            c.setFont("Helvetica", 9)

        student_name = alert.student.full_name if alert.student else ''
        detected = alert.detected_at.strftime('%d/%m/%Y %H:%M')
        line = f"{detected} | {alert.severity} | {student_name} | {alert.status}"
        c.drawString(40, y, line[:120])
        y -= 12

        excerpt = (alert.alert_excerpt or '').replace('\n', ' ')
        if excerpt:
            c.setFont("Helvetica-Oblique", 8)
            c.drawString(40, y, excerpt[:140])
            c.setFont("Helvetica", 9)
            y -= 12

    c.showPage()
    c.save()
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='alertes_report.pdf',
    )


# ---------------------------------------------------------------------------
# SETTINGS API (Student)
# ---------------------------------------------------------------------------
@app.route('/api/settings', methods=['PUT'])
@login_required
def api_update_settings():
    data = request.get_json()
    if data.get('language_pref') in ('fr', 'ar'):
        g.current_user.language_pref = data['language_pref']
    if 'notifications_enabled' in data:
        g.current_user.notifications_enabled = bool(data['notifications_enabled'])
    db.session.commit()
    return jsonify({'user': g.current_user.to_dict()})


@app.route('/api/settings/delete-data', methods=['POST'])
@login_required
@role_required('ELEVE')
def api_delete_data():
    """Delete all conversations and messages for the current student."""
    convs = Conversation.query.filter_by(user_id=g.current_user.id).all()
    for c in convs:
        Message.query.filter_by(conversation_id=c.id).delete()
        db.session.delete(c)
    db.session.commit()
    return jsonify({'message': 'Donnees supprimees avec succes'})


@app.route('/api/settings/export-data')
@login_required
@role_required('ELEVE')
def api_export_data():
    convs = Conversation.query.filter_by(user_id=g.current_user.id).order_by(
        Conversation.started_at.desc()
    ).all()

    export_convs = []
    for conv in convs:
        messages = []
        for msg in conv.messages:
            try:
                content = decrypt_message(msg.content_encrypted, Config.ENCRYPTION_KEY)
            except Exception:
                content = ''
            messages.append({
                'sender': msg.sender,
                'content': content,
                'timestamp': msg.timestamp.isoformat(),
            })
        export_convs.append({
            'id': conv.id,
            'started_at': conv.started_at.isoformat(),
            'emotion_initial': conv.emotion_initial,
            'messages': messages,
        })

    response = make_response(jsonify({'conversations': export_convs}))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = 'attachment; filename=mes_conversations.json'
    return response


@app.route('/api/settings/deactivate', methods=['POST'])
@login_required
@role_required('ELEVE')
def api_deactivate_account():
    g.current_user.is_active = False
    db.session.commit()
    resp = make_response(jsonify({'message': 'Compte desactive'}))
    resp.delete_cookie('auth_token')
    return resp


# ---------------------------------------------------------------------------
# DB Initialization & seed data
# ---------------------------------------------------------------------------
def init_db():
    """Create tables and seed demo data."""
    db.create_all()

    # Only seed if no users exist
    if User.query.first():
        return

    logger.info("Seeding database with demo data...")

    # Create classes
    class_3a = Class(name='3eme A', level='College')
    class_3b = Class(name='3eme B', level='College')
    class_1bac = Class(name='1ere Bac Sciences', level='Qualifiant')
    db.session.add_all([class_3a, class_3b, class_1bac])
    db.session.flush()

    # Create admin
    admin = User(
        email='admin@school.ma',
        password_hash=hash_password('admin123'),
        role='ADMIN',
        full_name='Administrateur Systeme',
        language_pref='fr',
    )

    # Create teachers
    teacher1 = User(
        email='prof@school.ma',
        password_hash=hash_password('prof123'),
        role='ENSEIGNANT',
        full_name='Mme Fatima Zahra',
        class_id=class_3a.id,
        language_pref='fr',
    )
    teacher2 = User(
        email='prof2@school.ma',
        password_hash=hash_password('prof123'),
        role='ENSEIGNANT',
        full_name='M. Ahmed Bennani',
        class_id=class_3b.id,
        language_pref='fr',
    )

    # Create students
    student1 = User(
        email='eleve1@school.ma',
        password_hash=hash_password('eleve123'),
        role='ELEVE',
        full_name='Youssef El Amrani',
        class_id=class_3a.id,
        language_pref='fr',
    )
    student2 = User(
        email='eleve2@school.ma',
        password_hash=hash_password('eleve123'),
        role='ELEVE',
        full_name='Khadija Benkirane',
        class_id=class_3a.id,
        language_pref='fr',
    )
    student3 = User(
        email='eleve3@school.ma',
        password_hash=hash_password('eleve123'),
        role='ELEVE',
        full_name='Omar Tazi',
        class_id=class_3b.id,
        language_pref='ar',
    )

    db.session.add_all([admin, teacher1, teacher2, student1, student2, student3])

    # Default system settings
    defaults = {
        'alert_recipient_default': Config.ALERT_RECIPIENT_DEFAULT,
        'alert_recipient_critique': Config.ALERT_RECIPIENT_CRITIQUE,
        'alert_recipient_elevee': Config.ALERT_RECIPIENT_ELEVEE,
        'alert_recipient_moderee': Config.ALERT_RECIPIENT_MODEREE,
        'data_retention_days': str(Config.DATA_RETENTION_DAYS),
    }
    for key, value in defaults.items():
        if not db.session.get(SystemSetting, key):
            db.session.add(SystemSetting(key=key, value=value or ''))

    db.session.commit()
    logger.info("Demo data seeded successfully!")
    logger.info("  Admin: admin@school.ma / admin123")
    logger.info("  Teacher: prof@school.ma / prof123")
    logger.info("  Student: eleve1@school.ma / eleve123")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, port=5000)
