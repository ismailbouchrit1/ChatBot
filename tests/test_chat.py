from app import chat_service
from alerts import AlertService


def test_chat_send(client, monkeypatch):
    monkeypatch.setattr(chat_service, 'get_response', lambda *args, **kwargs: 'Bonjour')
    monkeypatch.setattr(chat_service, 'analyze_message', lambda *args, **kwargs: {
        'language': 'fr',
        'sentiment': 'neutral',
        'emotion': 'neutre',
        'confidence': 0.7,
        'topics': ['ecole']
    })
    monkeypatch.setattr(AlertService, 'process_dual_detection', lambda *args, **kwargs: None)

    login = client.post('/api/auth/login', json={'email': 'student@school.ma', 'password': 'student123'})
    assert login.status_code == 200

    res = client.post('/api/chat/send', json={'message': 'Salut'})
    assert res.status_code == 200
    data = res.get_json()
    assert 'response' in data
