"""Analytics: Rollups for dashboards (rebuildable, referenced by nothing).

Postgres schema: analytics
Planned tables: materialized views and summary tables

Conventions:
  * inherit core.models.BaseModel (uuidv7 id) or TenantModel (org-owned + RLS)
  * Meta.db_table = table("analytics", "<name>")  ->  "analytics"."<name>"
"""

from core.db import table  # noqa: F401
from core.models import BaseModel, TenantModel  # noqa: F401

SCHEMA = "analytics"
