"""Import every module's models so ``Base.metadata`` is complete for Alembic.

Add one line here when a module introduces tables.
"""

import app.modules.audit.models
import app.modules.authorization.models
import app.modules.company.models
import app.modules.content.models
import app.modules.crm.models
import app.modules.identity.models
import app.modules.integrations.models
import app.modules.notifications.models
import app.modules.people.models
import app.modules.products.models
import app.modules.work.models  # noqa: F401
from app.db.base import Base

__all__ = ["Base"]
