"""Added gender field to the user model

Revision ID: 722e6242bff0
Revises: 59cec05170fe
Create Date: 2025-04-15 15:02:04.340936

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '722e6242bff0'
down_revision = '59cec05170fe'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('member', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gender', sa.String(length=10), nullable=False, server_default='Male'))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('member', schema=None) as batch_op:
        batch_op.drop_column('gender')

    # ### end Alembic commands ###
