# Database Migration Guidelines

This file provides guidance for working with Flask-Migrate and Alembic database migrations.

## Migration Workflow

### Creating Migrations
```bash
# Always activate virtual environment first
source venv/bin/activate

# Generate migration after model changes
flask db migrate -m "descriptive message about changes"

# Example migration messages:
flask db migrate -m "add booking_teams table"
flask db migrate -m "add email_verified column to members"
flask db migrate -m "create index on booking_date"
```

### Reviewing Migrations
**ALWAYS review generated migrations before applying:**

1. Check the generated migration file in `versions/`
2. Verify the upgrade() and downgrade() functions
3. Ensure data integrity considerations are handled
4. Test complex migrations on development data first

### Applying Migrations
```bash
# Apply migrations to database
flask db upgrade

# Apply specific migration
flask db upgrade <revision_id>

# Rollback to previous migration
flask db downgrade
```

## Migration Best Practices

### Naming Conventions
- Use descriptive migration messages
- Follow format: "action description"
- Examples:
  - "add user_preferences table"
  - "remove deprecated status column"
  - "create index on email field"

### Data Safety
- **ALWAYS backup database before major migrations**
- Test migrations on development/staging first
- Consider data migration needs for existing records
- Handle nullable/non-nullable column changes carefully

#### Adding NOT NULL Columns with Default Values
**CRITICAL**: SQLite cannot add NOT NULL columns with default values directly. Use this pattern:

**❌ BAD - Will fail with SQLite:**
```python
def upgrade():
    op.add_column('member', sa.Column('lockout', sa.Boolean(), nullable=False, default=False))
```
**Error**: `Cannot add a NOT NULL column with default value NULL`

**✅ GOOD - Three-step process:**
```python
def upgrade():
    # Step 1: Add column as nullable with default
    op.add_column('member', sa.Column('lockout', sa.Boolean(), nullable=True, default=False))
    
    # Step 2: Update existing rows to have the default value
    op.execute("UPDATE member SET lockout = 0 WHERE lockout IS NULL")
    
    # Step 3: Make the column NOT NULL
    op.alter_column('member', 'lockout', nullable=False)
```

**Why this happens**: SQLite requires a multi-step process to add NOT NULL columns to tables with existing data. The `default=False` parameter only applies to new INSERT operations, not existing rows.

### Complex Migrations
For complex schema changes:
1. Create migration with schema changes
2. Add data migration logic if needed
3. Test thoroughly before production

```python
# Example data migration in upgrade()
def upgrade():
    # Schema changes
    op.add_column('members', sa.Column('full_name', sa.String(128)))
    
    # Data migration
    connection = op.get_bind()
    connection.execute(
        "UPDATE members SET full_name = firstname || ' ' || lastname"
    )
```

## Migration Files

### File Structure
- `versions/` - Contains all migration files
- Each file has unique revision ID
- Includes upgrade() and downgrade() functions
- Migration dependencies tracked automatically

### Manual Migration Editing
When manually editing migrations:
- Understand Alembic operations
- Test both upgrade() and downgrade()
- Consider data preservation
- Update migration message if needed

### Common Operations
```python
# Add column
op.add_column('table_name', sa.Column('new_column', sa.String(50)))

# Remove column
op.drop_column('table_name', 'old_column')

# Add index
op.create_index('idx_booking_date', 'bookings', ['booking_date'])

# Add foreign key
op.create_foreign_key('fk_booking_event', 'bookings', 'events', ['event_id'], ['id'])
```

## Troubleshooting

### Common Issues
1. **Merge conflicts in migrations**
   - Resolve by creating new merge migration
   - `flask db merge -m "merge migrations"`

2. **Migration fails midway**
   - Check database state
   - May need to manually fix and mark as applied
   - Use `flask db stamp <revision>` if needed

3. **Alembic version mismatch**
   - Check current database version: `flask db current`
   - Sync with migration files: `flask db stamp head`

### Recovery Procedures
```bash
# Check current migration status
flask db current

# Show migration history
flask db history

# Mark specific migration as applied (use carefully)
flask db stamp <revision_id>

# Force migration to specific version (dangerous)
flask db upgrade <revision_id> --sql  # Preview SQL first
```

## Development vs Production

### Development
- Frequent small migrations are fine
- Can squash migrations if needed
- Test data migration scenarios

### Production
- **ALWAYS backup before migration**
- Plan downtime for major schema changes
- Test migration path thoroughly
- Have rollback plan ready
- Monitor application after migration

### Migration Deployment
1. Stop application (if needed)
2. Backup database
3. Apply migrations: `flask db upgrade`
4. Verify schema changes
5. Start application
6. Monitor for issues

## Database Schema Management

### Version Control
- All migration files committed to repository
- Never edit committed migrations
- Use merge migrations for collaboration

### Schema Documentation
- Keep models.py as source of truth
- Document complex relationships
- Maintain data integrity constraints

### Performance Considerations
- Add indexes for frequently queried columns
- Consider migration impact on large tables
- Plan for minimal downtime strategies