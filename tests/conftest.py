import pytest

from app import app as flask_app
from auth import hash_password
from models import db, User, Class


@pytest.fixture
def app():
    flask_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )

    with flask_app.app_context():
        db.create_all()

        school_class = Class(name='Test 1', level='College')
        db.session.add(school_class)
        db.session.flush()

        student = User(
            email='student@school.ma',
            password_hash=hash_password('student123'),
            role='ELEVE',
            full_name='Test Student',
            class_id=school_class.id,
        )
        teacher = User(
            email='teacher@school.ma',
            password_hash=hash_password('teacher123'),
            role='ENSEIGNANT',
            full_name='Test Teacher',
            class_id=school_class.id,
        )
        admin = User(
            email='admin@school.ma',
            password_hash=hash_password('admin123'),
            role='ADMIN',
            full_name='Test Admin',
        )
        db.session.add_all([student, teacher, admin])
        db.session.commit()

        yield flask_app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
