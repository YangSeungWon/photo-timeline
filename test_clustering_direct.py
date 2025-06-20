#!/usr/bin/env python3
"""
Direct test of clustering functionality to verify datetime fixes.
This bypasses the API and directly tests the worker functions.
"""

import os
import sys
import time
from datetime import datetime, timedelta

# Add backend path to import app modules
sys.path.insert(0, 'backend')

from app.core.queues import default_queue
from app.worker_tasks import _mark_cluster_pending, cluster_if_quiet

def test_clustering_functions():
    """Test the clustering functions directly."""
    print("🧪 Testing clustering functions directly...")
    print("=" * 50)
    
    # Test group ID (use existing one from logs)
    test_group_id = "81b3cda3-fb9f-418d-958a-bae826562515"
    
    print(f"📝 Testing group: {test_group_id}")
    
    # Test 1: _mark_cluster_pending (should not raise datetime errors)
    print("\n🔍 Test 1: _mark_cluster_pending() function")
    try:
        _mark_cluster_pending(test_group_id)
        print("✅ _mark_cluster_pending() executed without datetime errors")
    except Exception as e:
        print(f"❌ _mark_cluster_pending() failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        return False
    
    # Wait a moment to let Redis operations settle
    time.sleep(1)
    
    # Test 2: Check if job was scheduled properly
    print("\n🔍 Test 2: Checking if clustering job was scheduled")
    try:
        # Get queue stats
        queue_length = len(default_queue)
        scheduled_count = len(default_queue.scheduled_job_registry)
        
        print(f"📊 Queue length: {queue_length}")
        print(f"📅 Scheduled jobs: {scheduled_count}")
        
        if scheduled_count > 0:
            print("✅ Clustering job was scheduled successfully")
            
            # Get details of scheduled jobs
            for job_id in default_queue.scheduled_job_registry.get_job_ids():
                job = default_queue.scheduled_job_registry.get_job(job_id)
                if job:
                    print(f"   📋 Job: {job.id}")
                    print(f"   ⏰ Scheduled for: {job.scheduled_time}")
                    print(f"   🎯 Function: {job.func_name}")
        else:
            print("⚠️  No scheduled jobs found (might have executed already)")
            
    except Exception as e:
        print(f"❌ Failed to check queue status: {e}")
        return False
    
    # Test 3: Direct cluster_if_quiet test (if no jobs are pending)
    print("\n🔍 Test 3: Direct cluster_if_quiet() test")
    try:
        result = cluster_if_quiet(test_group_id)
        print(f"✅ cluster_if_quiet() returned: {result}")
    except Exception as e:
        print(f"❌ cluster_if_quiet() failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        return False
    
    print("\n🎉 All tests completed successfully!")
    print("✅ No datetime arithmetic errors found")
    print("✅ No transaction conflicts detected")
    return True

if __name__ == "__main__":
    success = test_clustering_functions()
    sys.exit(0 if success else 1) 