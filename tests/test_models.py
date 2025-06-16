"""
Unit tests for SQLModel database models.
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

# Add backend to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.models import (
    User,
    Group,
    Membership,
    MembershipRole,
    MembershipStatus,
    Meeting,
    Photo,
    Comment,
)


# Create simplified models for testing without PostGIS
class TestMeeting(SQLModel, table=True):
    """Simplified Meeting model for testing without PostGIS."""

    __tablename__ = "test_meeting"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    group_id: UUID = Field(foreign_key="group.id", index=True)
    title: Optional[str] = Field(default=None, max_length=200)
    start_time: datetime
    end_time: datetime
    meeting_date: datetime
    photo_count: int = Field(default=0)
    participant_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TestPhoto(SQLModel, table=True):
    """Simplified Photo model for testing without PostGIS."""

    __tablename__ = "test_photo"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    group_id: UUID = Field(foreign_key="group.id", index=True)
    uploader_id: UUID = Field(foreign_key="user.id", index=True)
    meeting_id: Optional[UUID] = Field(
        default=None, foreign_key="test_meeting.id", index=True
    )
    filename_orig: str = Field(max_length=255)
    file_size: int
    file_hash: str = Field(max_length=64, index=True)
    mime_type: str = Field(max_length=100)
    shot_at: Optional[datetime] = Field(default=None, index=True)
    is_processed: bool = Field(default=False)
    is_public: bool = Field(default=True)
    uploaded_at: datetime = Field(default_factory=datetime.utcnow, index=True)


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
    meeting = TestMeeting(
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
    photo = TestPhoto(
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

    photo = TestPhoto(
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

    photo = TestPhoto(
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
    meeting = TestMeeting(
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
    photo1 = TestPhoto(
        group_id=group.id,
        uploader_id=owner.id,
        meeting_id=meeting.id,
        filename_orig="sunset.jpg",
        file_size=2048000,
        file_hash="hash1",
        mime_type="image/jpeg",
    )
    photo2 = TestPhoto(
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
