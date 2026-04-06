from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings

_JWT = settings.SIMPLE_JWT


def get_tokens_for_user(user) -> dict:
    """Generate access + refresh token pair for a user."""
    refresh = RefreshToken.for_user(user)

    refresh['email']          = user.email
    refresh['employee_title'] = user.employee_title
    refresh['is_staff']       = user.is_staff
    refresh['is_superuser']   = user.is_superuser

    return {
        'access':  str(refresh.access_token),
        'refresh': str(refresh),
    }


def set_jwt_cookies(response, tokens: dict) -> None:
    """Attach both tokens as HttpOnly cookies to any Django response/redirect."""
    response.set_cookie(
        key      = _JWT.get('AUTH_COOKIE', 'access_token'),
        value    = tokens['access'],
        max_age  = int(_JWT.get('ACCESS_TOKEN_LIFETIME').total_seconds()),
        secure   = _JWT.get('AUTH_COOKIE_SECURE', True),
        httponly = _JWT.get('AUTH_COOKIE_HTTP_ONLY', True),
        samesite = _JWT.get('AUTH_COOKIE_SAMESITE', 'Lax'),
    )
    response.set_cookie(
        key      = _JWT.get('AUTH_COOKIE_REFRESH', 'refresh_token'),
        value    = tokens['refresh'],
        max_age  = int(_JWT.get('REFRESH_TOKEN_LIFETIME').total_seconds()),
        secure   = _JWT.get('AUTH_COOKIE_SECURE', True),
        httponly = _JWT.get('AUTH_COOKIE_HTTP_ONLY', True),
        samesite = _JWT.get('AUTH_COOKIE_SAMESITE', 'Lax'),
    )


def delete_jwt_cookies(response) -> None:
    """Expire both JWT cookies — call this in logoutView."""
    response.delete_cookie(_JWT.get('AUTH_COOKIE', 'access_token'))
    response.delete_cookie(_JWT.get('AUTH_COOKIE_REFRESH', 'refresh_token'))