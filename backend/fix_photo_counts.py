#!/usr/bin/env python3
"""
One-time data repair script to fix photo_count inconsistencies.

This script:
1. Recalculates photo_count for ALL meetings based on actual photo records
2. Identifies and reports meetings with mismatched counts
3. Removes empty meetings (except Default Meeting)
4. Provides detailed statistics

Usage:
    python fix_photo_counts.py [--dry-run] [--remove-empty]
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import Session, select, func
from app.core.database import engine
from app.models.meeting import Meeting
from app.models.photo import Photo
from app.models.group import Group


def fix_photo_counts(dry_run: bool = False, remove_empty: bool = False) -> dict:
    """
    Fix photo_count inconsistencies across all meetings.
    
    Args:
        dry_run: If True, only report issues without making changes
        remove_empty: If True, remove empty meetings (except Default Meeting)
        
    Returns:
        Statistics dictionary
    """
    stats = {
        "total_meetings": 0,
        "fixed_meetings": 0,
        "empty_meetings": 0,
        "removed_meetings": 0,
        "total_photos": 0,
        "before_sum": 0,
        "after_sum": 0,
        "changes": []
    }
    
    with Session(engine) as session:
        # Get all meetings
        meetings = session.exec(select(Meeting)).all()
        stats["total_meetings"] = len(meetings)
        
        # Calculate total photos
        stats["total_photos"] = session.exec(
            select(func.count(Photo.id))
        ).first() or 0
        
        print(f"🔍 Found {stats['total_meetings']} meetings, {stats['total_photos']} total photos")
        print("=" * 60)
        
        empty_meetings_to_remove = []
        
        for meeting in meetings:
            # Count actual photos in this meeting
            actual_count = session.exec(
                select(func.count(Photo.id)).where(Photo.meeting_id == meeting.id)
            ).first() or 0
            
            stats["before_sum"] += meeting.photo_count
            
            # Check for mismatch
            if meeting.photo_count != actual_count:
                change_info = {
                    "meeting_id": str(meeting.id),
                    "title": meeting.title,
                    "old_count": meeting.photo_count,
                    "new_count": actual_count,
                    "group_id": str(meeting.group_id)
                }
                stats["changes"].append(change_info)
                stats["fixed_meetings"] += 1
                
                print(f"📊 {meeting.title[:30]:30} | {meeting.photo_count:3d} → {actual_count:3d} | "
                      f"Δ{actual_count - meeting.photo_count:+3d}")
                
                if not dry_run:
                    meeting.photo_count = actual_count
                    meeting.updated_at = datetime.utcnow()
                    session.add(meeting)
            
            # Track empty meetings
            if actual_count == 0:
                stats["empty_meetings"] += 1
                if meeting.title != "Default Meeting" and remove_empty:
                    empty_meetings_to_remove.append(meeting)
                    print(f"🗑️  Will remove empty meeting: {meeting.title}")
            
            stats["after_sum"] += actual_count
        
        # Remove empty meetings if requested
        if remove_empty and not dry_run:
            for meeting in empty_meetings_to_remove:
                session.delete(meeting)
                stats["removed_meetings"] += 1
                print(f"❌ Removed empty meeting: {meeting.title}")
        
        # Commit changes
        if not dry_run:
            session.commit()
            print(f"✅ Committed {stats['fixed_meetings']} fixes and {stats['removed_meetings']} removals")
        else:
            print(f"🔍 DRY RUN: Would fix {stats['fixed_meetings']} meetings")
    
    return stats


def print_summary(stats: dict, dry_run: bool):
    """Print detailed summary of the fix operation."""
    print("\n" + "=" * 60)
    print("📈 SUMMARY")
    print("=" * 60)
    print(f"Total meetings:      {stats['total_meetings']:6d}")
    print(f"Fixed meetings:      {stats['fixed_meetings']:6d}")
    print(f"Empty meetings:      {stats['empty_meetings']:6d}")
    print(f"Removed meetings:    {stats['removed_meetings']:6d}")
    print(f"Total photos:        {stats['total_photos']:6d}")
    print(f"Before sum(counts):  {stats['before_sum']:6d}")
    print(f"After sum(counts):   {stats['after_sum']:6d}")
    
    # Validation
    if stats["after_sum"] == stats["total_photos"]:
        print("✅ VALIDATION: sum(photo_count) == count(*) FROM photo")
    else:
        print(f"❌ VALIDATION FAILED: Expected {stats['total_photos']}, got {stats['after_sum']}")
    
    if stats["changes"]:
        print(f"\n📋 TOP CHANGES:")
        for change in sorted(stats["changes"], key=lambda x: abs(x["new_count"] - x["old_count"]), reverse=True)[:10]:
            delta = change["new_count"] - change["old_count"]
            print(f"  {change['title'][:40]:40} {change['old_count']:3d} → {change['new_count']:3d} ({delta:+d})")
    
    if dry_run:
        print(f"\n🔍 This was a DRY RUN. Run without --dry-run to apply changes.")


def main():
    parser = argparse.ArgumentParser(description="Fix photo_count inconsistencies")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Only report issues, don't make changes")
    parser.add_argument("--remove-empty", action="store_true",
                       help="Remove empty meetings (except Default Meeting)")
    
    args = parser.parse_args()
    
    print("🔧 Photo Count Repair Tool")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE UPDATE'}")
    if args.remove_empty:
        print("🗑️  Will remove empty meetings")
    print()
    
    try:
        stats = fix_photo_counts(dry_run=args.dry_run, remove_empty=args.remove_empty)
        print_summary(stats, args.dry_run)
        
        if not args.dry_run:
            print("\n🎉 Photo count repair completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during repair: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 