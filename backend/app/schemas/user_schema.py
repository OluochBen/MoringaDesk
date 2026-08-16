from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from ..models import User

class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    email = fields.Email(required=True, validate=validate.Length(max=255))
    role = fields.Str(validate=validate.OneOf(['student', 'admin']))
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

class UserRegistrationSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    email = fields.Email(required=True, validate=validate.Length(max=255))
    password = fields.Str(required=True, validate=validate.Length(min=6))
    role = fields.Str(load_only=True, validate=validate.Equal('student'))
    
    @validates_schema
    def validate_email_unique(self, data, **kwargs):
        if User.query.filter_by(email=data['email']).first():
            raise ValidationError('Email already exists', 'email')

class UserLoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)
