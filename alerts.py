"""Alert detection service: dual mechanism (Gemini tag + keyword analysis) and email notification."""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from models import db, Alert, User, SystemSetting
from config import Config

logger = logging.getLogger(__name__)

# Weighted critical keywords for secondary detection (French + Arabic)
CRITICAL_KEYWORDS = {
    # Suicidal ideation (weight 8-10)
    'suicide': 10, 'suicider': 10, 'me suicider': 10, 'envie de mourir': 10,
    'plus envie de vivre': 10, 'mourir': 8, 'mort': 6, 'tuer': 8,
    'fin a ma vie': 10, 'fin a tout': 9, 'plus la peine': 8,
    'je veux disparaitre': 9, 'disparaitre': 7,

    # Self-harm (weight 7-10)
    'automutilation': 10, 'me couper': 9, 'me faire du mal': 9,
    'me blesser': 8, 'scarification': 10, 'me bruler': 9,

    # Violence & abuse (weight 7-10)
    'frapper': 6, 'violence': 7, 'battre': 7, 'me bat': 8,
    'abus': 8, 'abus sexuel': 10, 'attouchement': 10, 'viol': 10,
    'agression': 8, 'agresse': 8, 'touche de force': 10,

    # Severe depression (weight 5-7)
    'depression': 6, 'deprime': 5, 'desespoir': 7, 'desespere': 7,
    'plus de raison': 8, 'sans espoir': 7, 'rien ne va': 5,

    # Bullying (weight 6-8)
    'harcelement': 7, 'harcele': 7, 'harceler': 7, 'intimide': 6,
    'menace': 6, 'menaces': 6, 'frappent chaque jour': 9,

    # Arabic keywords
    '\u0627\u0646\u062a\u062d\u0627\u0631': 10,        # suicide
    '\u0645\u0648\u062a': 8,            # death
    '\u0642\u062a\u0644': 8,            # kill
    '\u0639\u0646\u0641': 7,            # violence
    '\u062a\u062d\u0631\u0634': 10,         # harassment/abuse
    '\u0627\u0643\u062a\u0626\u0627\u0628': 6,        # depression
    '\u064a\u0623\u0633': 7,            # despair
    '\u0627\u063a\u062a\u0635\u0627\u0628': 10,       # rape
    '\u0623\u0630\u064a\u0629': 8,          # harm
    '\u0636\u0631\u0628': 7,            # beating
}

ALERT_THRESHOLD_CRITIQUE = 8
ALERT_THRESHOLD_ELEVEE = 6
ALERT_THRESHOLD_MODEREE = 4


class AlertService:
    @staticmethod
    def _get_setting_value(key: str, fallback: str = '') -> str:
        try:
            setting = db.session.get(SystemSetting, key)
            return setting.value if setting and setting.value is not None else fallback
        except Exception:
            return fallback

    @staticmethod
    def _parse_recipients(value: str) -> list[str]:
        if not value:
            return []
        return [email.strip() for email in value.split(',') if email.strip()]

    @staticmethod
    def _get_severity_recipients(severity: str) -> list[str]:
        if severity == 'CRITIQUE':
            value = AlertService._get_setting_value(
                'alert_recipient_critique', Config.ALERT_RECIPIENT_CRITIQUE
            )
        elif severity == 'ELEVEE':
            value = AlertService._get_setting_value(
                'alert_recipient_elevee', Config.ALERT_RECIPIENT_ELEVEE
            )
        else:
            value = AlertService._get_setting_value(
                'alert_recipient_moderee', Config.ALERT_RECIPIENT_MODEREE
            )
        return AlertService._parse_recipients(value)

    @staticmethod
    def analyze_message(message_text: str) -> tuple[str | None, int]:
        """Analyze a student message for critical content using keyword matching.

        Returns:
            Tuple of (severity or None, score)
            severity: 'CRITIQUE', 'ELEVEE', 'MODEREE', or None
        """
        text_lower = message_text.lower()
        score = 0
        matched = []

        for keyword, weight in CRITICAL_KEYWORDS.items():
            if keyword in text_lower:
                score += weight
                matched.append(keyword)

        if score >= ALERT_THRESHOLD_CRITIQUE:
            severity = 'CRITIQUE'
        elif score >= ALERT_THRESHOLD_ELEVEE:
            severity = 'ELEVEE'
        elif score >= ALERT_THRESHOLD_MODEREE:
            severity = 'MODEREE'
        else:
            severity = None

        if matched:
            logger.info("Alert keywords detected (score=%d): %s", score, matched)

        return severity, score

    @staticmethod
    def create_alert(student_id: str, conversation_id: str, severity: str,
                     excerpt: str) -> Alert:
        """Create an alert record in the database."""
        # Find the appropriate teacher to notify
        student = db.session.get(User, student_id)
        notified_user = None
        if student and student.class_id:
            notified_user = User.query.filter_by(
                class_id=student.class_id, role='ENSEIGNANT', is_active=True
            ).first()
        # Fallback to admin
        if not notified_user:
            notified_user = User.query.filter_by(role='ADMIN', is_active=True).first()

        alert = Alert(
            student_id=student_id,
            conversation_id=conversation_id,
            severity=severity,
            detected_at=datetime.now(timezone.utc),
            alert_excerpt=excerpt[:500],  # Limit excerpt length
            status='NOUVELLE',
            notified_user_id=notified_user.id if notified_user else None,
        )
        db.session.add(alert)
        db.session.commit()

        # Attempt email notification (non-blocking)
        try:
            AlertService._send_email_notification(alert, student, notified_user)
        except Exception as e:
            logger.error("Failed to send alert email: %s", str(e))

        return alert

    @staticmethod
    def _send_email_notification(alert: Alert, student: User, recipient: User):
        """Send email notification for an alert (best-effort)."""
        if not Config.SMTP_SERVER or not Config.SMTP_USER:
            logger.warning("SMTP not configured, skipping email notification")
            return

        default_email = AlertService._get_setting_value(
            'alert_recipient_default', Config.ALERT_RECIPIENT_DEFAULT
        )
        recipient_email = recipient.email if recipient else default_email
        recipients = []
        if recipient_email:
            recipients.append(recipient_email)

        recipients.extend(AlertService._get_severity_recipients(alert.severity))
        recipients = list(dict.fromkeys([r for r in recipients if r]))
        if not recipients:
            return

        msg = MIMEMultipart()
        msg['From'] = Config.SMTP_USER
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = f"[ALERTE {alert.severity}] Chatbot Socio-Emotionnel - {student.full_name}"

        body = f"""
        ALERTE {alert.severity} - Chatbot Socio-Emotionnel

        Eleve: {student.full_name}
        Classe: {student.school_class.name if student.school_class else 'Non assignee'}
        Date: {alert.detected_at.strftime('%d/%m/%Y %H:%M')}
        Gravite: {alert.severity}

        Extrait: {alert.alert_excerpt}

        Veuillez consulter le tableau de bord pour plus de details et prendre les mesures appropriees.
        """

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        try:
            with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
                server.starttls()
                server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                server.send_message(msg)
                logger.info("Alert email sent to %s", msg['To'])
        except Exception as e:
            logger.error("SMTP error: %s", str(e))

    @staticmethod
    def process_dual_detection(student_message: str, bot_response: str,
                               student_id: str, conversation_id: str) -> Alert | None:
        """Run dual detection: Gemini tag + keyword analysis.

        Alert is triggered if EITHER detection is positive.
        """
        from chat_service import ChatService

        # Detection 1: Check Gemini response for alert tag
        gemini_detected = ChatService.check_alert_tag(bot_response)

        # Detection 2: Keyword-based analysis of student message
        keyword_severity, keyword_score = AlertService.analyze_message(student_message)

        # Determine final severity
        if gemini_detected:
            final_severity = 'CRITIQUE'  # Gemini detection = always critical
        elif keyword_severity:
            final_severity = keyword_severity
        else:
            return None  # No alert

        # Create excerpt from student message (truncated for privacy)
        excerpt = student_message[:300]
        if len(student_message) > 300:
            excerpt += '...'

        logger.warning(
            "ALERT triggered for student %s: severity=%s, gemini=%s, keywords=%s (score=%d)",
            student_id, final_severity, gemini_detected, keyword_severity, keyword_score
        )

        return AlertService.create_alert(
            student_id=student_id,
            conversation_id=conversation_id,
            severity=final_severity,
            excerpt=excerpt,
        )
