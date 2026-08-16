import secrets, datetime
from flask_jwt_extended import create_access_token
from marshmallow import ValidationError
from .. import db
from ..models import User, PasswordResetToken
from ..schemas import UserRegistrationSchema, UserLoginSchema
from ..utils.email_utils import send_reset_email


class AuthService:
    @staticmethod
    def register_user(data):
        schema = UserRegistrationSchema()
        try:
            validated = schema.load(data)
        except ValidationError as err:
            return {'error': err.messages}, 400

        user = User(
            name=validated['name'],
            email=validated['email'],
            role='student'
        )
        user.set_password(validated['password'])
        db.session.add(user)
        db.session.commit()

        access_token = create_access_token(identity=str(user.id))
        return {'user': user.to_dict(), 'access_token': access_token}, 201

    @staticmethod
    def login_user(data):
        schema = UserLoginSchema()
        try:
            validated = schema.load(data)
        except ValidationError as err:
            return {'error': err.messages}, 400

        user = User.query.filter_by(email=validated['email']).first()
        if not user or not user.check_password(validated['password']):
            return {'error': 'Invalid email or password'}, 401

        access_token = create_access_token(identity=str(user.id))
        return {'user': user.to_dict(), 'access_token': access_token}, 200

    @staticmethod
    def get_user_by_id(user_id):
        return User.query.get(user_id)

    # --- Password reset flow
    @staticmethod
    def request_password_reset(email):
        user = User.query.filter_by(email=email).first()
        if not user:
            return {'error': 'User not found'}, 404

        # Invalidate any previous tokens
        PasswordResetToken.query.filter_by(user_id=user.id, used=False).delete()

        token = secrets.token_urlsafe(32)
        reset = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        )
        db.session.add(reset)
        db.session.commit()

        # Send reset email with token
        send_reset_email(user.email, token)
        return {'message': 'Password reset email sent'}, 200

    @staticmethod
    def reset_password(token, new_password):
        reset = PasswordResetToken.query.filter_by(token=token).first()
        if not reset or not reset.is_valid():
            return {'error': 'Invalid or expired token'}, 400

        user = User.query.get(reset.user_id)
        if not user:
            return {'error': 'User not found'}, 404

        # Update password
        user.set_password(new_password)

        # Mark token as used
        reset.used = True
        reset.used_at = datetime.datetime.utcnow()

        db.session.commit()
        return {'message': 'Password updated successfully'}, 200
