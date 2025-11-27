# myapp/middleware.py

from urllib.parse import parse_qs
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token):
    """
    Decode a JWT access token and return the authenticated user.
    """
    try:
        validated_token = UntypedToken(token)
        user_id = validated_token.get("user_id")
        if not user_id:
            return AnonymousUser()
        return User.objects.get(pk=user_id)
    except (InvalidToken, TokenError, KeyError, User.DoesNotExist):
        return AnonymousUser()


class QueryStringTokenAuthMiddleware:
    """
    Custom middleware to authenticate WebSocket connections using
    ?token=<JWT_ACCESS_TOKEN> in the query string.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if token:
            scope["user"] = await get_user_from_token(token)
        else:
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)


def TokenAuthMiddlewareStack(inner):
    """
    Shortcut wrapper to combine Django AuthMiddlewareStack
    with the custom QueryString JWT auth.
    """
    from channels.auth import AuthMiddlewareStack
    return QueryStringTokenAuthMiddleware(AuthMiddlewareStack(inner))
