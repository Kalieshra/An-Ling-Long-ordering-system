"""Serializers for auth API endpoints."""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Role, User


class UserSerializer(serializers.ModelSerializer):
    """Summary serializer used in register/login responses."""

    name = serializers.CharField(source="first_name", read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "role", "name", "phone")
        read_only_fields = ("id", "role", "name")


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for the authenticated user's own profile.
    `email` and `role` are read-only — the user cannot self-promote."""

    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "phone", "role")
        read_only_fields = ("id", "email", "role")


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_email(self, value):
        normalized = User.objects.normalize_email(value).lower()  # full lowercase
        if User.objects.filter(email=normalized).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return normalized

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages)) from e
        return value

    def create(self, validated_data):
        # Role is *always* customer for public registration.
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data["name"],
            phone=validated_data.get("phone", ""),
            role=Role.CUSTOMER,
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        # Mirror the storage normalization (UserManager._create_user lowercases the
        # full address). DRF's EmailField does not lowercase, so without this hook
        # logging in with any capital letters would fail to match the stored row.
        return User.objects.normalize_email(value).lower()


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages)) from e
        return value
