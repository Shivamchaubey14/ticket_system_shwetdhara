from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from django.conf import settings


class JWTCookieAuthentication(JWTAuthentication):
    """
    Reads the JWT access token from an HttpOnly cookie instead of
    the Authorization header, so it works with Django template views.
    """

    def authenticate(self, request):
        cookie_name = getattr(settings, 'SIMPLE_JWT', {}).get('AUTH_COOKIE', 'access_token')
        raw_token = request.COOKIES.get(cookie_name)

        if raw_token is None:
            return None  # no token — fall through to session auth

        try:
            validated_token = self.get_validated_token(raw_token)
        except (TokenError, InvalidToken):
            return None  # expired/invalid — let the view handle redirect

        return self.get_user(validated_token), validated_token