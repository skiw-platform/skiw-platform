# No models. Django sends `post_migrate` only for apps that have a models module
# (django.core.management.sql.emit_post_migrate_signal), and tenancy.keys needs it (plan M4c-3).
