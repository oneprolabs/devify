from dj_rest_auth.registration.views import (
    RegisterView,
    SocialConnectView,
    SocialLoginView,
    VerifyEmailView,
)
from dj_rest_auth.views import LoginView, LogoutView, PasswordChangeView
from django.urls import path
from rest_framework.permissions import AllowAny

from accounts.views import (
    CheckVirtualEmailUsernameView,
    CompleteGoogleSetupView,
    CompleteRegistrationView,
    ConfirmPasswordResetView,
    CustomTokenRefreshView,
    CustomUserDetailsView,
    GetAvailableScenesView,
    SendPasswordResetEmailView,
    SendRegistrationEmailView,
    VerifyRegistrationTokenView,
)
from accounts.views.desktop_auth import (
    DesktopAuthorizeAPIView,
    DesktopConfigAPIView,
    DesktopDeviceListAPIView,
    DesktopDeviceRevokeAPIView,
    DesktopTokenAPIView,
)


class CustomLoginView(LoginView):
    permission_classes = [AllowAny]


urlpatterns = [
    # Login endpoint
    path("api/v1/auth/login", CustomLoginView.as_view(), name="rest_login"),
    # Logout endpoint
    path("api/v1/auth/logout", LogoutView.as_view(), name="rest_logout"),
    path(
        "api/v1/auth/token/refresh",
        CustomTokenRefreshView.as_view(),
        name="rest_token_refresh",
    ),
    path(
        "api/v1/auth/desktop/authorize",
        DesktopAuthorizeAPIView.as_view(),
        name="desktop_authorize",
    ),
    path(
        "api/v1/auth/desktop/config",
        DesktopConfigAPIView.as_view(),
        name="desktop_config",
    ),
    path(
        "api/v1/auth/desktop/token",
        DesktopTokenAPIView.as_view(),
        name="desktop_token",
    ),
    path(
        "api/v1/auth/desktop/devices",
        DesktopDeviceListAPIView.as_view(),
        name="desktop_devices",
    ),
    path(
        "api/v1/auth/desktop/devices/<str:device_id>",
        DesktopDeviceRevokeAPIView.as_view(),
        name="desktop_device_revoke",
    ),
    # Get or update user details
    path(
        "api/v1/auth/user",
        CustomUserDetailsView.as_view(),
        name="rest_user_details",
    ),
    # Request password reset (custom implementation)
    path(
        "api/v1/auth/password/reset",
        SendPasswordResetEmailView.as_view(),
        name="rest_password_reset",
    ),
    # Confirm password reset (custom implementation)
    path(
        "api/v1/auth/password/reset/confirm",
        ConfirmPasswordResetView.as_view(),
        name="rest_password_reset_confirm",
    ),
    # Change password
    path(
        "api/v1/auth/password/change",
        PasswordChangeView.as_view(),
        name="rest_password_change",
    ),
    # Register new user
    path(
        "api/v1/auth/registration",
        RegisterView.as_view(),
        name="rest_register",
    ),
    # Verify email after registration
    path(
        "api/v1/auth/registration/verify-email",
        VerifyEmailView.as_view(),
        name="rest_verify_email",
    ),
    # Social login endpoint
    path(
        "api/v1/auth/social/login",
        SocialLoginView.as_view(),
        name="social_login",
    ),
    # Social connect endpoint
    path(
        "api/v1/auth/social/connect",
        SocialConnectView.as_view(),
        name="social_connect",
    ),
    # Social disconnect endpoint (uncomment if needed)
    # path(
    #     'api/v1/auth/social/disconnect',
    #     SocialDisconnectView.as_view(),
    #     name='social_disconnect'
    # ),
    # Custom registration endpoints
    path(
        "api/v1/auth/register/send-email",
        SendRegistrationEmailView.as_view(),
        name="register_send_email",
    ),
    path(
        "api/v1/auth/register/verify-token/<str:token>",
        VerifyRegistrationTokenView.as_view(),
        name="register_verify_token",
    ),
    path(
        "api/v1/auth/register/complete",
        CompleteRegistrationView.as_view(),
        name="register_complete",
    ),
    path(
        "api/v1/auth/check-username/<str:username>",
        CheckVirtualEmailUsernameView.as_view(),
        name="check_username",
    ),
    # OAuth complete setup (generic for all OAuth providers)
    path(
        "api/v1/auth/oauth/complete-setup",
        CompleteGoogleSetupView.as_view(),
        name="oauth_complete_setup",
    ),
    # Backward compatibility: Google-specific endpoint
    path(
        "api/v1/auth/google/complete-setup",
        CompleteGoogleSetupView.as_view(),
        name="google_complete_setup",
    ),
    # Utility endpoints
    path(
        "api/v1/auth/scenes",
        GetAvailableScenesView.as_view(),
        name="available_scenes",
    ),
]
