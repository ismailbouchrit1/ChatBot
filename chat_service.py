"""Gemini API chat service integration using google-genai SDK."""
import os
import json
import logging
import re
from google import genai
from config import Config

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self):
        self.system_prompt = self._load_system_prompt()
        self._client = None

    def _get_client(self):
        if self._client is None and Config.GEMINI_API_KEY:
            self._client = genai.Client(api_key=Config.GEMINI_API_KEY)
        return self._client

    def _load_system_prompt(self):
        prompt_path = os.path.join(os.path.dirname(__file__), 'prompts', 'system_prompt_v3.txt')
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error("System prompt file not found at %s", prompt_path)
            return ""

    def get_response(self, user_message: str, history: list = None) -> str:
        """Send a message to Gemini and get a response.

        Args:
            user_message: The student's message
            history: List of dicts with 'sender' (ELEVE/CHATBOT) and 'content' keys

        Returns:
            The chatbot's response text
        """
        client = self._get_client()
        if not client:
            return ("Je suis desole, le service est temporairement indisponible. "
                    "Veuillez reessayer plus tard.")

        try:
            # Build conversation contents
            contents = []
            if history:
                for msg in history:
                    role = "user" if msg['sender'] == 'ELEVE' else "model"
                    contents.append({"role": role, "parts": [{"text": msg['content']}]})

            # Add current user message
            contents.append({"role": "user", "parts": [{"text": user_message}]})

            response = client.models.generate_content(
                model=Config.GEMINI_MODEL,
                contents=contents,
                config={
                    "system_instruction": self.system_prompt,
                    "temperature": 0.7,
                    "max_output_tokens": 500,
                }
            )
            return response.text

        except Exception as e:
            logger.error("Gemini API error: %s", str(e))
            return ("Je rencontre un probleme technique en ce moment. "
                    "N'hesite pas a reessayer dans quelques instants.")

    def analyze_message(self, user_message: str, history: list = None) -> dict:
        """Analyze language, sentiment, emotion, and topics from the conversation."""
        client = self._get_client()
        if not client:
            return {}

        analysis_prompt = (
            "Retourne UNIQUEMENT un JSON valide, sans texte autour.\n"
            "Champs obligatoires: language, sentiment, emotion, confidence, topics.\n"
            "language: code court (fr, ar, darija, mix).\n"
            "sentiment: positive, neutral, negative, critical.\n"
            "emotion: serein, bien, stresse, anxieux, triste, en_colere, fatigue, confus, neutre.\n"
            "confidence: nombre entre 0 et 1.\n"
            "topics: liste de 1 a 3 mots ou expressions courtes (sans phrases)."
        )

        history_text = self._format_history(history)
        analysis_input = (
            f"Historique (recent):\n{history_text}\n\n"
            f"Message eleve:\n{user_message}"
        )

        try:
            response = client.models.generate_content(
                model=Config.GEMINI_MODEL,
                contents=[{
                    "role": "user",
                    "parts": [{"text": f"{analysis_prompt}\n\n{analysis_input}"}],
                }],
                config={
                    "temperature": 0.1,
                    "max_output_tokens": 200,
                }
            )
        except Exception as e:
            logger.error("Gemini analysis error: %s", str(e))
            return {}

        return self._safe_parse_json(response.text) or {}

    @staticmethod
    def _format_history(history: list, max_items: int = 8) -> str:
        if not history:
            return ""
        recent = history[-max_items:]
        lines = []
        for msg in recent:
            sender = msg.get('sender', 'UNKNOWN')
            content = msg.get('content', '')
            lines.append(f"{sender}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _safe_parse_json(text: str) -> dict | None:
        if not text:
            return None
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def check_alert_tag(response_text: str) -> bool:
        """Check if the Gemini response contains the critical alert tag."""
        return '[ALERTE_CRITIQUE_DECLENCHEE]' in response_text

    @staticmethod
    def clean_response(response_text: str) -> str:
        """Remove the alert tag from the displayed response."""
        return response_text.replace('[ALERTE_CRITIQUE_DECLENCHEE]', '').strip()
