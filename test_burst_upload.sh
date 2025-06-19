#!/bin/bash

# Burst Upload Test Script
# Tests the debounced clustering functionality by uploading multiple photos rapidly

set -e

# Configuration
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
GROUP_ID="${GROUP_ID:-your-group-id-here}"
JWT_TOKEN="${JWT_TOKEN:-your-jwt-token-here}"
PHOTO_COUNT="${PHOTO_COUNT:-10}"
UPLOAD_DELAY="${UPLOAD_DELAY:-0.1}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Photo Timeline - Burst Upload Test${NC}"
echo "================================================"
echo "API Base URL: $API_BASE_URL"
echo "Group ID: $GROUP_ID"
echo "Photo Count: $PHOTO_COUNT"
echo "Upload Delay: ${UPLOAD_DELAY}s"
echo "================================================"

# Check if required parameters are set
if [[ "$GROUP_ID" == "your-group-id-here" ]]; then
    echo -e "${RED}❌ Error: Please set GROUP_ID environment variable${NC}"
    echo "Example: export GROUP_ID='11111111-1111-1111-1111-111111111111'"
    exit 1
fi

if [[ "$JWT_TOKEN" == "your-jwt-token-here" ]]; then
    echo -e "${RED}❌ Error: Please set JWT_TOKEN environment variable${NC}"
    echo "Example: export JWT_TOKEN='eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'"
    exit 1
fi

# Create test images directory
TEST_DIR="/tmp/photo_timeline_test"
mkdir -p "$TEST_DIR"

# Generate test images using ImageMagick (if available) or create dummy files
echo -e "${YELLOW}📸 Generating test images...${NC}"

if command -v convert &> /dev/null; then
    # Use ImageMagick to create actual images with different timestamps
    for i in $(seq 1 $PHOTO_COUNT); do
        timestamp=$(date -d "2024-01-01 10:00:00 +${i} minutes" '+%Y:%m:%d %H:%M:%S')
        convert -size 800x600 xc:lightblue \
                -pointsize 40 \
                -draw "text 50,100 'Test Photo ${i}'" \
                -draw "text 50,150 'Time: ${timestamp}'" \
                "$TEST_DIR/photo_${i}.jpg"
    done
    echo -e "${GREEN}✅ Generated $PHOTO_COUNT test images with ImageMagick${NC}"
else
    # Create dummy files if ImageMagick is not available
    echo -e "${YELLOW}⚠️  ImageMagick not found, creating dummy files${NC}"
    for i in $(seq 1 $PHOTO_COUNT); do
        # Create a small dummy JPEG-like file
        echo -e "\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB\x00C\x00" > "$TEST_DIR/photo_${i}.jpg"
        echo "Test Photo $i - $(date)" >> "$TEST_DIR/photo_${i}.jpg"
    done
    echo -e "${GREEN}✅ Generated $PHOTO_COUNT dummy files${NC}"
fi

# Function to upload a single photo
upload_photo() {
    local photo_num=$1
    local photo_path="$TEST_DIR/photo_${photo_num}.jpg"
    
    echo -e "${BLUE}📤 Uploading photo ${photo_num}...${NC}"
    
    response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Authorization: Bearer $JWT_TOKEN" \
        -F "file=@$photo_path" \
        -F "group_id=$GROUP_ID" \
        "$API_BASE_URL/api/photos/upload")
    
    http_code=$(echo "$response" | tail -n1)
    response_body=$(echo "$response" | head -n -1)
    
    if [[ "$http_code" == "200" ]]; then
        echo -e "${GREEN}✅ Photo ${photo_num} uploaded successfully${NC}"
        return 0
    else
        echo -e "${RED}❌ Photo ${photo_num} upload failed (HTTP $http_code)${NC}"
        echo "Response: $response_body"
        return 1
    fi
}

# Upload photos in burst
echo -e "${YELLOW}🔥 Starting burst upload...${NC}"
start_time=$(date +%s)
failed_uploads=0

for i in $(seq 1 $PHOTO_COUNT); do
    if ! upload_photo "$i"; then
        ((failed_uploads++))
    fi
    
    # Add delay between uploads (except for the last one)
    if [[ $i -lt $PHOTO_COUNT ]]; then
        sleep "$UPLOAD_DELAY"
    fi
done

end_time=$(date +%s)
duration=$((end_time - start_time))

echo "================================================"
echo -e "${BLUE}📊 Upload Summary${NC}"
echo "Total photos: $PHOTO_COUNT"
echo "Failed uploads: $failed_uploads"
echo "Successful uploads: $((PHOTO_COUNT - failed_uploads))"
echo "Total duration: ${duration}s"
echo "Average upload rate: $(echo "scale=2; $PHOTO_COUNT / $duration" | bc -l) photos/sec"
echo "================================================"

# Wait for clustering to complete
echo -e "${YELLOW}⏳ Waiting for clustering to complete...${NC}"
echo "This may take 5-10 seconds depending on CLUSTER_DEBOUNCE_TTL and CLUSTER_RETRY_DELAY settings"

# Sleep for the debounce period + retry delay + some buffer
sleep_time=$((${CLUSTER_DEBOUNCE_TTL:-5} + ${CLUSTER_RETRY_DELAY:-3} + 3))
echo "Sleeping for ${sleep_time} seconds..."
sleep "$sleep_time"

# Check cluster results (if API endpoint is available)
echo -e "${BLUE}🔍 Checking clustering results...${NC}"
echo "You can manually check the results by:"
echo "1. Looking at the worker logs for clustering activity"
echo "2. Querying the meetings API: GET $API_BASE_URL/api/meetings?group_id=$GROUP_ID"
echo "3. Checking Redis keys: cluster:pending:$GROUP_ID, cluster:count:$GROUP_ID"

# Cleanup
echo -e "${YELLOW}🧹 Cleaning up test files...${NC}"
rm -rf "$TEST_DIR"
echo -e "${GREEN}✅ Cleanup complete${NC}"

echo -e "${GREEN}🎉 Burst upload test completed!${NC}"
echo ""
echo -e "${BLUE}Expected behavior:${NC}"
echo "- Only ONE clustering job should have been executed"  
echo "- All photos should be grouped into appropriate meetings"
echo "- Redis keys should be cleaned up after clustering"
echo ""
echo -e "${YELLOW}Check the worker logs to verify debounced clustering worked correctly.${NC}" 