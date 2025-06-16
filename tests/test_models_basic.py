"""
Basic unit tests for SQLModel database models without PostGIS.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlmodel import SQLModel, Field
from datetime import datetime
from uuid import UUID, uuid4
import sys
import os
from typing import Optional
from enum import Enum

# Add backend to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))


class MembershipRole(str, Enum):
    """Membership roles within a group."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    PENDING = "pending"


class MembershipStatus(str, Enum):
    """Membership status."""

    ACTIVE = "active"
    PENDING = "pending"
    SUSPENDED = "suspended"
    LEFT = "left"


class User(SQLModel, table=True):
    """User model for authentication and profile management."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=50)
    email: str = Field(unique=True, index=True, max_length=255)
    full_name: str = Field(max_length=100)

    # Authentication
    hashed_password: str
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    last_login: Optional[datetime] = Field(default=None)

    # Profile
    avatar_filename: Optional[str] = Field(default=None, max_length=255)
    timezone: str = Field(default="UTC", max_length=50)


class Group(SQLModel, table=True):
    """Group model for organizing users into photo-sharing communities."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=100, index=True)
    description: Optional[str] = Field(default=None, max_length=500)

    # Group settings
    is_private: bool = Field(default=True)
    require_approval: bool = Field(default=True)
    max_members: Optional[int] = Field(default=None)

    # Ownership
    owner_id: UUID = Field(foreign_key="user.id")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)

    # Group image
    cover_photo_filename: Optional[str] = Field(default=None, max_length=255)


class Membership(SQLModel, table=True):
    """Membership model for user-group relationships."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Foreign keys
    user_id: UUID = Field(foreign_key="user.id")
    group_id: UUID = Field(foreign_key="group.id")

    # Membership details
    role: MembershipRole = Field(default=MembershipRole.MEMBER)
    status: MembershipStatus = Field(default=MembershipStatus.PENDING)

    # Timestamps
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = Field(default=None)
    left_at: Optional[datetime] = Field(default=None)

    # Approval tracking
    approved_by: Optional[UUID] = Field(default=None, foreign_key="user.id")


class Meeting(SQLModel, table=True):
    """Meeting model representing a cluster of photos taken around the same time."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Group association
    group_id: UUID = Field(foreign_key="group.id", index=True)

    # Meeting metadata
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)

    # Time range (automatically calculated from photos)
    start_time: datetime
    end_time: datetime
    meeting_date: datetime  # Primary date for grouping (usually start_time date)

    # Statistics
    photo_count: int = Field(default=0)
    participant_count: int = Field(default=0)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)


class Photo(SQLModel, table=True):
    """Photo model with EXIF data (without PostGIS)."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Associations
    group_id: UUID = Field(foreign_key="group.id", index=True)
    uploader_id: UUID = Field(foreign_key="user.id", index=True)
    meeting_id: Optional[UUID] = Field(
        default=None, foreign_key="meeting.id", index=True
    )

    # File information
    filename_orig: str = Field(max_length=255)
    filename_thumb: Optional[str] = Field(default=None, max_length=255)
    filename_medium: Optional[str] = Field(default=None, max_length=255)
    file_size: int  # Size in bytes
    file_hash: str = Field(max_length=64, index=True)  # SHA-256 hash for deduplication
    mime_type: str = Field(max_length=100)

    # Photo metadata from EXIF
    shot_at: Optional[datetime] = Field(default=None, index=True)
    camera_make: Optional[str] = Field(default=None, max_length=100)
    camera_model: Optional[str] = Field(default=None, max_length=100)

    # Image dimensions
    width: Optional[int] = Field(default=None)
    height: Optional[int] = Field(default=None)
    orientation: Optional[int] = Field(default=None)  # EXIF orientation

    # GPS data as simple lat/lon (no PostGIS)
    gps_latitude: Optional[float] = Field(default=None)
    gps_longitude: Optional[float] = Field(default=None)
    gps_altitude: Optional[float] = Field(default=None)

    # User annotations
    caption: Optional[str] = Field(default=None, max_length=1000)
    tags: Optional[str] = Field(default=None, max_length=500)  # Comma-separated tags

    # Processing status
    is_processed: bool = Field(default=False)
    processing_error: Optional[str] = Field(default=None, max_length=500)

    # Timestamps
    uploaded_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: Optional[datetime] = Field(default=None)

    # Privacy and moderation
    is_public: bool = Field(default=True)
    is_flagged: bool = Field(default=False)
    flagged_reason: Optional[str] = Field(default=None, max_length=200)


class Comment(SQLModel, table=True):
    """Comment model for threaded discussions on photos."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Associations
    photo_id: UUID = Field(foreign_key="photo.id", index=True)
    author_id: UUID = Field(foreign_key="user.id", index=True)

    # Threading support
    parent_id: Optional[UUID] = Field(default=None, foreign_key="comment.id")
    thread_root_id: Optional[UUID] = Field(
        default=None, foreign_key="comment.id", index=True
    )
    depth: int = Field(default=0)  # Nesting level (0 = top-level comment)

    # Comment content
    content: str = Field(max_length=2000)

    # Moderation
    is_edited: bool = Field(default=False)
    is_deleted: bool = Field(default=False)
    is_flagged: bool = Field(default=False)
    flagged_reason: Optional[str] = Field(default=None, max_length=200)

    # Engagement metrics
    like_count: int = Field(default=0)
    reply_count: int = Field(default=0)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)

    # Sorting and display
    sort_order: int = Field(default=0)  # For custom ordering within threads


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(engine):
    """Create a database session for testing."""
    with Session(engine) as session:
        yield session


def test_user_creation(db_session):
    """Test creating a user."""
    user = User(
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        hashed_password="hashed_password_here",
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.is_active is True
    assert user.is_superuser is False
    assert user.created_at is not None


def test_group_creation(db_session):
    """Test creating a group."""
    # First create a user to be the owner
    owner = User(
        username="owner",
        email="owner@example.com",
        full_name="Group Owner",
        hashed_password="hashed_password",
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    # Create the group
    group = Group(name="Test Group", description="A test group", owner_id=owner.id)

    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)

    assert group.id is not None
    assert group.name == "Test Group"
    assert group.owner_id == owner.id
    assert group.is_private is True
    assert group.require_approval is True


def test_membership_creation(db_session):
    """Test creating a membership relationship."""
    # Create user and group
    user = User(
        username="member",
        email="member@example.com",
        full_name="Member User",
        hashed_password="hashed_password",
    )
    owner = User(
        username="owner",
        email="owner@example.com",
        full_name="Owner User",
        hashed_password="hashed_password",
    )
    db_session.add_all([user, owner])
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(owner)

    group = Group(name="Test Group", owner_id=owner.id)
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)

    # Create membership
    membership = Membership(
        user_id=user.id,
        group_id=group.id,
        role=MembershipRole.MEMBER,
        status=MembershipStatus.ACTIVE,
    )

    db_session.add(membership)
    db_session.commit()
    db_session.refresh(membership)

    assert membership.id is not None
    assert membership.user_id == user.id
    assert membership.group_id == group.id
    assert membership.role == MembershipRole.MEMBER
    assert membership.status == MembershipStatus.ACTIVE


def test_meeting_creation(db_session):
    """Test creating a meeting."""
    # Create prerequisites
    owner = User(
        username="owner",
        email="owner@example.com",
        full_name="Owner",
        hashed_password="hashed_password",
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    group = Group(name="Test Group", owner_id=owner.id)
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)

    # Create meeting
    now = datetime.utcnow()
    meeting = Meeting(
        group_id=group.id,
        title="Test Meeting",
        start_time=now,
        end_time=now,
        meeting_date=now,
    )

    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    assert meeting.id is not None
    assert meeting.group_id == group.id
    assert meeting.title == "Test Meeting"
    assert meeting.photo_count == 0
    assert meeting.participant_count == 0


def test_photo_creation(db_session):
    """Test creating a photo."""
    # Create prerequisites
    owner = User(
        username="owner",
        email="owner@example.com",
        full_name="Owner",
        hashed_password="hashed_password",
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    group = Group(name="Test Group", owner_id=owner.id)
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)

    # Create photo
    photo = Photo(
        group_id=group.id,
        uploader_id=owner.id,
        filename_orig="test.jpg",
        file_size=1024000,
        file_hash="abc123def456",
        mime_type="image/jpeg",
    )

    db_session.add(photo)
    db_session.commit()
    db_session.refresh(photo)

    assert photo.id is not None
    assert photo.group_id == group.id
    assert photo.uploader_id == owner.id
    assert photo.filename_orig == "test.jpg"
    assert photo.is_processed is False
    assert photo.is_public is True
    assert photo.uploaded_at is not None


def test_photo_with_gps(db_session):
    """Test creating a photo with GPS coordinates."""
    # Create prerequisites
    owner = User(
        username="owner",
        email="owner@example.com",
        full_name="Owner",
        hashed_password="hashed_password",
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    group = Group(name="Test Group", owner_id=owner.id)
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)

    # Create photo with GPS
    photo = Photo(
        group_id=group.id,
        uploader_id=owner.id,
        filename_orig="gps_photo.jpg",
        file_size=2048000,
        file_hash="gps123hash456",
        mime_type="image/jpeg",
        gps_latitude=37.7749,
        gps_longitude=-122.4194,
        gps_altitude=100.5,
    )

    db_session.add(photo)
    db_session.commit()
    db_session.refresh(photo)

    assert photo.gps_latitude == 37.7749
    assert photo.gps_longitude == -122.4194
    assert photo.gps_altitude == 100.5


def test_comment_creation(db_session):
    """Test creating a comment."""
    # Create prerequisites
    owner = User(
        username="owner",
        email="owner@example.com",
        full_name="Owner",
        hashed_password="hashed_password",
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    group = Group(name="Test Group", owner_id=owner.id)
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)

    photo = Photo(
        group_id=group.id,
        uploader_id=owner.id,
        filename_orig="test.jpg",
        file_size=1024000,
        file_hash="abc123def456",
        mime_type="image/jpeg",
    )
    db_session.add(photo)
    db_session.commit()
    db_session.refresh(photo)

    # Create comment
    comment = Comment(
        photo_id=photo.id, author_id=owner.id, content="This is a test comment!"
    )

    db_session.add(comment)
    db_session.commit()
    db_session.refresh(comment)

    assert comment.id is not None
    assert comment.photo_id == photo.id
    assert comment.author_id == owner.id
    assert comment.content == "This is a test comment!"
    assert comment.depth == 0
    assert comment.like_count == 0
    assert comment.reply_count == 0
    assert comment.is_deleted is False


def test_threaded_comments(db_session):
    """Test creating threaded comments."""
    # Create prerequisites
    owner = User(
        username="owner",
        email="owner@example.com",
        full_name="Owner",
        hashed_password="hashed_password",
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    group = Group(name="Test Group", owner_id=owner.id)
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)

    photo = Photo(
        group_id=group.id,
        uploader_id=owner.id,
        filename_orig="test.jpg",
        file_size=1024000,
        file_hash="abc123def456",
        mime_type="image/jpeg",
    )
    db_session.add(photo)
    db_session.commit()
    db_session.refresh(photo)

    # Create parent comment
    parent_comment = Comment(
        photo_id=photo.id, author_id=owner.id, content="Parent comment"
    )
    db_session.add(parent_comment)
    db_session.commit()
    db_session.refresh(parent_comment)

    # Create reply comment
    reply_comment = Comment(
        photo_id=photo.id,
        author_id=owner.id,
        content="Reply comment",
        parent_id=parent_comment.id,
        thread_root_id=parent_comment.id,
        depth=1,
    )
    db_session.add(reply_comment)
    db_session.commit()
    db_session.refresh(reply_comment)

    assert reply_comment.parent_id == parent_comment.id
    assert reply_comment.thread_root_id == parent_comment.id
    assert reply_comment.depth == 1


def test_full_workflow(db_session):
    """Test a complete workflow with all models."""
    # Create users
    owner = User(
        username="owner",
        email="owner@example.com",
        full_name="Group Owner",
        hashed_password="hashed_password",
    )
    member = User(
        username="member",
        email="member@example.com",
        full_name="Group Member",
        hashed_password="hashed_password",
    )
    db_session.add_all([owner, member])
    db_session.commit()
    db_session.refresh(owner)
    db_session.refresh(member)

    # Create group
    group = Group(
        name="Photo Club", description="A photography group", owner_id=owner.id
    )
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)

    # Create memberships
    owner_membership = Membership(
        user_id=owner.id,
        group_id=group.id,
        role=MembershipRole.OWNER,
        status=MembershipStatus.ACTIVE,
    )
    member_membership = Membership(
        user_id=member.id,
        group_id=group.id,
        role=MembershipRole.MEMBER,
        status=MembershipStatus.ACTIVE,
    )
    db_session.add_all([owner_membership, member_membership])
    db_session.commit()

    # Create meeting
    now = datetime.utcnow()
    meeting = Meeting(
        group_id=group.id,
        title="Weekend Photowalk",
        start_time=now,
        end_time=now,
        meeting_date=now,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    # Create photos
    photo1 = Photo(
        group_id=group.id,
        uploader_id=owner.id,
        meeting_id=meeting.id,
        filename_orig="sunset.jpg",
        file_size=2048000,
        file_hash="hash1",
        mime_type="image/jpeg",
        gps_latitude=37.7749,
        gps_longitude=-122.4194,
    )
    photo2 = Photo(
        group_id=group.id,
        uploader_id=member.id,
        meeting_id=meeting.id,
        filename_orig="landscape.jpg",
        file_size=1536000,
        file_hash="hash2",
        mime_type="image/jpeg",
    )
    db_session.add_all([photo1, photo2])
    db_session.commit()
    db_session.refresh(photo1)
    db_session.refresh(photo2)

    # Create comments
    comment1 = Comment(
        photo_id=photo1.id, author_id=member.id, content="Beautiful sunset!"
    )
    comment2 = Comment(
        photo_id=photo2.id, author_id=owner.id, content="Great composition!"
    )
    db_session.add_all([comment1, comment2])
    db_session.commit()

    # Verify the complete workflow
    assert group.name == "Photo Club"
    assert len([owner_membership, member_membership]) == 2
    assert meeting.title == "Weekend Photowalk"
    assert len([photo1, photo2]) == 2
    assert len([comment1, comment2]) == 2
    assert photo1.gps_latitude == 37.7749
    assert photo1.gps_longitude == -122.4194
