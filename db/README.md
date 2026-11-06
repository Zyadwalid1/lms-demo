# Database

- `0001_foundation.sql` - schemas, extensions, grants, role settings. **Already applied** to Neon project
  Demo-LMS (`dev` and `production`, database `lms`). Kept for new branches and CI preview branches.
- Everything after the foundation (tables, indexes, RLS policies) is a **Django migration**, run with:

```bash
python manage.py migrate --database owner
```

Never run migrations through the pooled `DATABASE_URL`; the `owner` connection uses the direct host as `lms_owner`.
