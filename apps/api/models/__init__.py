# Import all SQLAlchemy models so Alembic can discover them via Base.metadata
from modules.auth.models import UserProfile, UserCredential  # noqa: F401
from modules.agent.models import Investigation  # noqa: F401
