def test_login_success(client):
    res = client.post('/api/auth/login', json={'email': 'student@school.ma', 'password': 'student123'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['user']['role'] == 'ELEVE'


def test_login_invalid(client):
    res = client.post('/api/auth/login', json={'email': 'student@school.ma', 'password': 'wrong'})
    assert res.status_code in (401, 423)
