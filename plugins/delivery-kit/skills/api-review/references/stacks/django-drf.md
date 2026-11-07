# Django REST Framework checklist

Use alongside the general checklist in the skill when `project.stack` is `django` or `django-drf`.

## Authorization
- Every view sets `permission_classes`; check for per-method permission maps (for example a `permission_map = {"GET": ..., "POST": ...}`) and that every HTTP method the view implements has an entry.
- `get_queryset()` or the service scopes rows by tenant or ownership. `get_object()` on an unscoped queryset is an IDOR.
- Custom permission classes implement `has_object_permission` where object access matters; DRF only calls it from `get_object()`.

## Serializers
- `ModelSerializer` with `fields = "__all__"` or writable nested serializers can expose or allow writes to fields the endpoint shouldn't touch.
- `read_only_fields` covers server-owned fields (status, owner, amounts).
- `source="a.b.c"` chains and `SerializerMethodField`s that hit relations cause per-row queries.
- Validation lives in `validate_<field>` / `validate` or the service, and is the same on create and update.

## ORM
- Relations used in serializers are in `select_related` / `prefetch_related` on the list queryset.
- Multi-step writes are wrapped in `transaction.atomic()`; check `ATOMIC_REQUESTS` in settings before assuming per-request transactions.
- Read-modify-write on balances, counters or statuses uses `select_for_update()` or `F()` expressions.
- `get_or_create` / `update_or_create` without a matching unique constraint can race into duplicates.
- `UniqueConstraint` including a nullable column doesn't prevent duplicates where that column is NULL (PostgreSQL); look for `nulls_distinct=False` or a conditional constraint.
- `bulk_create` / `bulk_update` / `queryset.update()` skip `save()` and signals; check that audit logging doesn't depend on them.

## Migrations
- `RemoveField`, `RenameField`, `DeleteModel`, `AlterField(null=False)` without a default, or removing a choice the running code still writes, break zero-downtime deploys if shipped with the code change.
- `AddIndex` on a large table should be `AddIndexConcurrently` (with `atomic = False`).
- `RunPython` data migrations are idempotent and have a reverse function or `migrations.RunPython.noop` with a reason.

## Async and signals
- Celery tasks are idempotent and safe to retry; tasks that take model instances should take ids.
- Signal receivers that write are covered by the same transaction, or use `transaction.on_commit`.
- Periodic tasks are registered the way the project registers them (for example a sync management command), not only in code.

## Tests
- `django_assert_num_queries` (pytest-django) or `assertNumQueries` on list endpoints, with several parent rows.
- Denial tests for each role that must not access the endpoint, and for cross-tenant access.
