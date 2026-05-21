def test_student_cannot_access_alerts(client):
    login = client.post('/api/auth/login', json={'email': 'student@school.ma', 'password': 'student123'})
    assert login.status_code == 200
    res = client.get('/api/alerts')
    assert res.status_code in (401, 403)


def test_teacher_can_access_alerts(client):
    login = client.post('/api/auth/login', json={'email': 'teacher@school.ma', 'password': 'teacher123'})
    assert login.status_code == 200
    res = client.get('/api/alerts')
    assert res.status_code == 200
