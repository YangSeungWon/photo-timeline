#!/bin/bash
set -e

# Test script to validate datetime and transaction fixes
# Creates burst uploads to trigger clustering without datetime arithmetic errors

echo "🚀 Testing fixes for datetime arithmetic and transaction conflicts"
echo "=================================================================="

# Configuration
API_BASE="http://localhost:8080/api"
GROUP_ID="81b3cda3-fb9f-418d-958a-bae826562515"  # Use existing group
TEST_IMAGE="frontend/public/test.jpg"

# Get authentication token
echo "📝 Getting authentication token..."
LOGIN_RESPONSE=$(curl -s -X POST "${API_BASE}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "testpass"}')

TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')
if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
    echo "❌ Failed to get auth token"
    exit 1
fi
echo "✅ Authentication successful"

# Check if test image exists
if [ ! -f "$TEST_IMAGE" ]; then
    echo "⚠️  Test image not found at $TEST_IMAGE, creating one..."
    # Create a simple test image using ImageMagick if available
    if command -v convert &> /dev/null; then
        convert -size 100x100 xc:blue "$TEST_IMAGE"
        echo "✅ Created test image"
    else
        echo "❌ No test image and ImageMagick not available"
        exit 1
    fi
fi

# Function to upload photo
upload_photo() {
    local photo_num=$1
    echo "📤 Uploading photo $photo_num..."
    
    RESPONSE=$(curl -s -X POST "${API_BASE}/photos/upload" \
      -H "Authorization: Bearer $TOKEN" \
      -F "file=@$TEST_IMAGE" \
      -F "group_id=$GROUP_ID")
    
    if echo "$RESPONSE" | jq -e '.id' > /dev/null; then
        echo "✅ Photo $photo_num uploaded successfully"
        return 0
    else
        echo "❌ Photo $photo_num upload failed: $RESPONSE"
        return 1
    fi
}

# Test burst uploads (should trigger clustering without datetime errors)
echo "🔥 Starting burst upload test (5 photos in quick succession)..."
for i in {1..5}; do
    upload_photo $i
    sleep 0.1  # Small delay to simulate real usage
done

echo "⏳ Waiting 5 seconds for worker processing..."
sleep 5

# Check Redis keys to see if debounce mechanism is working
echo "🔍 Checking Redis keys..."
docker exec photo-timeline-redis-1 redis-cli KEYS "cluster:*"

# Check worker logs for errors
echo "📋 Recent worker logs (last 20 lines):"
docker compose logs worker --tail=20

echo ""
echo "🎯 Test completed! Check the logs above for:"
echo "   ✅ Should NOT see: 'unsupported operand type(s) for +: datetime.datetime and int'"
echo "   ✅ Should NOT see: 'A transaction is already begun on this Session'"
echo "   ✅ Should see: Redis operations with emoji debug messages"
echo "   ✅ Should see: 'Successfully scheduled debounced clustering'" 