"""Added firstname and surname to members table

Revision ID: 875cde57901e
Revises: 1de28e8ae42d
Create Date: 2025-04-08 11:19:43.948590

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '875cde57901e'
down_revision = '1de28e8ae42d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('member', schema=None) as batch_op:
        batch_op.add_column(sa.Column('firstname', sa.String(length=64), nullable=False))
        batch_op.add_column(sa.Column('lastname', sa.String(length=64), nullable=False))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('member', schema=None) as batch_op:
        batch_op.drop_column('lastname')
        batch_op.drop_column('firstname')

    # ### end Alembic commands ###
