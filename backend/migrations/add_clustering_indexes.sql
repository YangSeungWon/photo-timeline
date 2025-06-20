-- Migration: Add indexes for efficient photo clustering operations
-- These indexes optimize the debounced batch clustering performance

-- Index for efficient meeting queries by group and end time (for latest meeting lookup)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_meeting_group_endtime 
    ON meeting (group_id, end_time DESC);

-- Index for efficient photo queries by group and shot_at (for clustering)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_photo_group_shot_at 
    ON photo (group_id, shot_at) 
    WHERE shot_at IS NOT NULL;

-- Index for efficient photo queries by meeting_id (for meeting photo counts)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_photo_meeting_id 
    ON photo (meeting_id);

-- Index for meeting date queries (for batch clustering by date)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_meeting_group_date 
    ON meeting (group_id, meeting_date);

-- Composite index for efficient meeting filtering (non-default meetings)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_meeting_group_title_created 
    ON meeting (group_id, title, created_at DESC) 
    WHERE title != 'Default Meeting';

-- Performance analysis queries (uncomment to check index usage)
-- EXPLAIN ANALYZE SELECT * FROM meeting WHERE group_id = 'uuid' ORDER BY end_time DESC LIMIT 1;
-- EXPLAIN ANALYZE SELECT * FROM photo WHERE group_id = 'uuid' AND shot_at IS NOT NULL ORDER BY shot_at;
-- EXPLAIN ANALYZE SELECT COUNT(*) FROM photo WHERE meeting_id = 'uuid'; 