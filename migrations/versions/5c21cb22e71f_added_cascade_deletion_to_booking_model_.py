"""added cascade deletion to Booking model to handle member deletions

Revision ID: 5c21cb22e71f
Revises: d7111c4414f0
Create Date: 2025-04-08 17:48:03.216237

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5c21cb22e71f'
down_revision = 'd7111c4414f0'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the existing foreign key constraint
    with op.batch_alter_table('booking', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_booking_member_id',  # Explicitly name the new constraint
            'member',  # Referenced table
            ['member_id'],  # Local column
            ['id'],  # Referenced column
            ondelete='CASCADE'  # Add cascade deletion
        )


def downgrade():
    # Revert the foreign key constraint to its original state
    with op.batch_alter_table('booking', schema=None) as batch_op:
        batch_op.drop_constraint('fk_booking_member_id', type_='foreignkey')  # Drop the named constraint
        batch_op.create_foreign_key(
            'fk_booking_member_id',  # Explicitly name the reverted constraint
            'member',  # Referenced table
            ['member_id'],  # Local column
            ['id']  # Referenced column
        )
