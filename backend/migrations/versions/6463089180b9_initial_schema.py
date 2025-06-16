"""initial schema

Revision ID: 6463089180b9
Revises:
Create Date: 2025-06-16 23:19:25.175050

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from geoalchemy2 import Geometry


# revision identifiers, used by Alembic.
revision: str = "6463089180b9"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create users table
    op.create_table(
        "user",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("avatar_filename", sa.String(length=255), nullable=True),
        sa.Column("timezone", sa.String(length=50), nullable=False, default="UTC"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(op.f("ix_user_email"), "user", ["email"], unique=False)
    op.create_index(op.f("ix_user_username"), "user", ["username"], unique=False)

    # Create groups table
    op.create_table(
        "group",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_private", sa.Boolean(), nullable=False, default=True),
        sa.Column("require_approval", sa.Boolean(), nullable=False, default=True),
        sa.Column("max_members", sa.Integer(), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("cover_photo_filename", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_group_name"), "group", ["name"], unique=False)

    # Create memberships table
    op.create_table(
        "membership",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            sa.Enum("owner", "admin", "member", "pending", name="membershiprole"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("active", "pending", "suspended", "left", name="membershipstatus"),
            nullable=False,
        ),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("left_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["group.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create meetings table
    op.create_table(
        "meeting",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("meeting_date", sa.DateTime(), nullable=False),
        sa.Column("track_gps", Geometry("LINESTRING", srid=4326), nullable=True),
        sa.Column("bbox_north", sa.Float(), nullable=True),
        sa.Column("bbox_south", sa.Float(), nullable=True),
        sa.Column("bbox_east", sa.Float(), nullable=True),
        sa.Column("bbox_west", sa.Float(), nullable=True),
        sa.Column("photo_count", sa.Integer(), nullable=False, default=0),
        sa.Column("participant_count", sa.Integer(), nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("cover_photo_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["group.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_meeting_group_id"), "meeting", ["group_id"], unique=False)

    # Create photos table
    op.create_table(
        "photo",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploader_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filename_orig", sa.String(length=255), nullable=False),
        sa.Column("filename_thumb", sa.String(length=255), nullable=True),
        sa.Column("filename_medium", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("shot_at", sa.DateTime(), nullable=True),
        sa.Column("camera_make", sa.String(length=100), nullable=True),
        sa.Column("camera_model", sa.String(length=100), nullable=True),
        sa.Column("lens_model", sa.String(length=100), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("orientation", sa.Integer(), nullable=True),
        sa.Column("aperture", sa.Float(), nullable=True),
        sa.Column("shutter_speed", sa.String(length=20), nullable=True),
        sa.Column("iso", sa.Integer(), nullable=True),
        sa.Column("focal_length", sa.Float(), nullable=True),
        sa.Column("flash", sa.Boolean(), nullable=True),
        sa.Column("point_gps", Geometry("POINT", srid=4326), nullable=True),
        sa.Column("gps_altitude", sa.Float(), nullable=True),
        sa.Column("gps_accuracy", sa.Float(), nullable=True),
        sa.Column("exif_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("tags", sa.String(length=500), nullable=True),
        sa.Column("is_processed", sa.Boolean(), nullable=False, default=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_flagged", sa.Boolean(), nullable=False, default=False),
        sa.Column("flagged_reason", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["group.id"],
        ),
        sa.ForeignKeyConstraint(
            ["meeting_id"],
            ["meeting.id"],
        ),
        sa.ForeignKeyConstraint(
            ["uploader_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_photo_file_hash"), "photo", ["file_hash"], unique=False)
    op.create_index(op.f("ix_photo_group_id"), "photo", ["group_id"], unique=False)
    op.create_index(op.f("ix_photo_meeting_id"), "photo", ["meeting_id"], unique=False)
    op.create_index(op.f("ix_photo_shot_at"), "photo", ["shot_at"], unique=False)
    op.create_index(
        op.f("ix_photo_uploaded_at"), "photo", ["uploaded_at"], unique=False
    )
    op.create_index(
        op.f("ix_photo_uploader_id"), "photo", ["uploader_id"], unique=False
    )

    # Create comments table
    op.create_table(
        "comment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("photo_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("thread_root_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("depth", sa.Integer(), nullable=False, default=0),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_edited", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_flagged", sa.Boolean(), nullable=False, default=False),
        sa.Column("flagged_reason", sa.String(length=200), nullable=True),
        sa.Column("like_count", sa.Integer(), nullable=False, default=0),
        sa.Column("reply_count", sa.Integer(), nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, default=0),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["comment.id"],
        ),
        sa.ForeignKeyConstraint(
            ["photo_id"],
            ["photo.id"],
        ),
        sa.ForeignKeyConstraint(
            ["thread_root_id"],
            ["comment.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_comment_author_id"), "comment", ["author_id"], unique=False
    )
    op.create_index(
        op.f("ix_comment_created_at"), "comment", ["created_at"], unique=False
    )
    op.create_index(op.f("ix_comment_photo_id"), "comment", ["photo_id"], unique=False)
    op.create_index(
        op.f("ix_comment_thread_root_id"), "comment", ["thread_root_id"], unique=False
    )

    # Add foreign key constraint for meeting cover photo (after photo table is created)
    op.create_foreign_key(None, "meeting", "photo", ["cover_photo_id"], ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order
    op.drop_table("comment")
    op.drop_table("photo")
    op.drop_table("meeting")
    op.drop_table("membership")
    op.drop_table("group")
    op.drop_table("user")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS membershipstatus")
    op.execute("DROP TYPE IF EXISTS membershiprole")
