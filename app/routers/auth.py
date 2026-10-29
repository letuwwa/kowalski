from datetime import UTC, datetime

from flask import Blueprint
from flask_jwt_extended import (
    create_access_token,
    current_user,
    get_jwt,
    jwt_required,
)
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db, limiter
from app.models import TokenBlocklist, User, UserRole
from app.routers.utils import (
    create_token_pair,
    json_body,
    login_identifier,
    string_value,
    validate_register_payload,
)
from app.routers.utils.auth import MAX_PASSWORD_LENGTH

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.post("/register", strict_slashes=False)
@limiter.limit("5 per hour")
def register():
    data = json_body()
    errors = validate_register_payload(data)
    if errors:
        return {"errors": errors}, 400

    email = data["email"].strip().lower()
    username = data["username"].strip().lower()

    existing_user = db.session.execute(
        select(User.id)
        .where(or_(User.email == email, User.username == username))
        .limit(1)
    ).scalar_one_or_none()
    if existing_user is not None:
        return {"message": "Email or username is already registered"}, 409

    user = User(
        email=email,
        username=username,
        first_name=data["first_name"].strip(),
        last_name=data["last_name"].strip(),
        is_active=True,
        role=UserRole.REGULAR,
    )
    user.set_password(data["password"])

    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing_user = db.session.execute(
            select(User.id)
            .where(or_(User.email == email, User.username == username))
            .limit(1)
        ).scalar_one_or_none()
        if existing_user is None:
            raise
        return {"message": "Email or username is already registered"}, 409

    return {"user": user.to_dict(), "tokens": create_token_pair(user)}, 201


@auth_bp.post("/login", strict_slashes=False)
@limiter.limit("10 per minute")
def login():
    data = json_body()
    identifier = login_identifier(data)
    password = string_value(data, "password")

    if (
        not identifier
        or len(identifier) > 255
        or not 1 <= len(password) <= MAX_PASSWORD_LENGTH
    ):
        return {"message": "Invalid credentials"}, 401

    user = db.session.execute(
        select(User).where(or_(User.email == identifier, User.username == identifier))
    ).scalar_one_or_none()
    if user is None or not user.check_password(password):
        return {"message": "Invalid credentials"}, 401

    if not user.is_active:
        return {"message": "User account is disabled"}, 403

    return {"user": user.to_dict(), "tokens": create_token_pair(user)}, 200


@auth_bp.post("/refresh", strict_slashes=False)
@jwt_required(refresh=True)
def refresh():
    if current_user is None:
        return {"message": "User not found"}, 401

    if not current_user.is_active:
        return {"message": "User account is disabled"}, 403

    token = get_jwt()
    additional_claims = {"role": current_user.role.value}
    if token.get("sid"):
        additional_claims.update(
            sid=token["sid"], sexp=token.get("sexp") or token["exp"]
        )
    access_token = create_access_token(
        identity=str(current_user.id),
        additional_claims=additional_claims,
    )
    return {"access_token": access_token}, 200


@auth_bp.post("/logout", strict_slashes=False)
@jwt_required(verify_type=False)
def logout():
    token = get_jwt()
    expires_at = datetime.fromtimestamp(
        max(token.get("sexp") or token["exp"], token["exp"]), tz=UTC
    )

    revoked_token = TokenBlocklist(
        jti=token["jti"],
        session_id=token.get("sid"),
        token_type=token["type"],
        user_id=token["sub"],
        expires_at=expires_at,
    )

    db.session.add(revoked_token)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        criteria = [TokenBlocklist.jti == token["jti"]]
        if token.get("sid"):
            criteria.append(TokenBlocklist.session_id == token["sid"])
        already_revoked = db.session.execute(
            select(TokenBlocklist.id).where(or_(*criteria)).limit(1)
        ).scalar_one_or_none()
        if already_revoked is None:
            raise

    return {"message": "Token revoked"}, 200


@auth_bp.get("/me", strict_slashes=False)
@jwt_required()
def me():
    if current_user is None:
        return {"message": "User not found"}, 401

    if not current_user.is_active:
        return {"message": "User account is disabled"}, 403

    return {"user": current_user.to_dict()}, 200


@auth_bp.get("/admin-only", strict_slashes=False)
@jwt_required()
def admin_only():
    if current_user is None:
        return {"message": "User not found"}, 401

    if not current_user.is_active:
        return {"message": "User account is disabled"}, 403

    if current_user.role != UserRole.ADMIN:
        return {"message": "Admin access required"}, 403

    return {
        "message": "Admin access granted",
        "user_id": str(current_user.id),
    }, 200
