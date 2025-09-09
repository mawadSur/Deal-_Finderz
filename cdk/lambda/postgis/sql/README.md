Place your SQL files here to be executed as migrations after PostGIS is enabled.

Rules:
- Files ending with `.sql` are executed in lexicographic order.
- A table `schema_migrations(id, executed_at)` is created to track applied files by filename.
- Each file may contain multiple statements separated by `;` (simple splitter).
- Idempotency is your responsibility; reruns are skipped by filename.

Examples:
- `001_create_tables.sql`
- `010_add_indexes.sql`
