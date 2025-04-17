"""Added Posts table

Revision ID: bd02b6922a9a
Revises: bef1f384308e
Create Date: 2025-04-17 15:57:15.265487

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bd02b6922a9a'
down_revision = 'bef1f384308e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('posts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('summary', sa.String(length=200), nullable=False),
    sa.Column('publish_on', sa.Date(), nullable=False),
    sa.Column('expires_on', sa.Date(), nullable=False),
    sa.Column('pin', sa.Boolean(), nullable=False),
    sa.Column('pin_until', sa.Date(), nullable=True),
    sa.Column('tags', sa.String(length=255), nullable=True),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('markdown_filename', sa.String(length=255), nullable=False),
    sa.Column('html_filename', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['member.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('posts')
    # ### end Alembic commands ###
