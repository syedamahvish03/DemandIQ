"""Shared test authentication override for processing API regression tests."""
import pytest

from backend.app.main import app, get_current_user


@pytest.fixture(autouse=True)
def authenticated_processing_api():
    """Keep existing endpoint tests focused on processing behavior, not Supabase I/O."""
    app.dependency_overrides[get_current_user] = lambda: {"id": "test-user-id"}
    yield
    app.dependency_overrides.pop(get_current_user, None)
