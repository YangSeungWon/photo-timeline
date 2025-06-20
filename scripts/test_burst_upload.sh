#!/bin/bash

# ================================
# 🧪 ENHANCED Photo Timeline Burst Upload Test
# ================================
# Tests the robustness of our debounced clustering system
# Validates: Transaction safety, datetime fixes, Redis resilience

set -e  # Exit on any error

# Configuration
API_BASE_URL="${API_BASE_URL:-http://localhost:3067/api/v1}"
GROUP_ID="${GROUP_ID:-your-group-id-here}"
JWT_TOKEN="${JWT_TOKEN:-your-jwt-token-here}"
PHOTO_COUNT="${PHOTO_COUNT:-10}"
UPLOAD_DELAY="${UPLOAD_DELAY:-0.1}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

# Test scenarios
TEST_SCENARIOS="${TEST_SCENARIOS:-burst,past,mixed}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Photo Timeline - Enhanced Clustering Test${NC}"
echo "================================================"
echo "API Base URL: $API_BASE_URL"
echo "Group ID: $GROUP_ID"
echo "Photo Count: $PHOTO_COUNT"
echo "Upload Delay: ${UPLOAD_DELAY}s"
echo "Test Scenarios: $TEST_SCENARIOS"
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

# Check Redis connection
check_redis() {
    if command -v redis-cli &> /dev/null; then
        echo -e "${BLUE}🔍 Checking Redis connection...${NC}"
        if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Redis connected${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  Redis not accessible at $REDIS_HOST:$REDIS_PORT${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️  redis-cli not found${NC}"
        return 1
    fi
}

# Monitor Redis keys
monitor_redis_keys() {
    if check_redis; then
        echo -e "${PURPLE}📊 Redis Keys:${NC}"
        echo "Pending: $(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" get "cluster:pending:$GROUP_ID" 2>/dev/null || echo 'none')"
        echo "Count: $(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" get "cluster:count:$GROUP_ID" 2>/dev/null || echo 'none')"
        echo "Job: $(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" exists "cluster:job:$GROUP_ID" 2>/dev/null || echo 'none')"
        echo "Pending TTL: $(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ttl "cluster:pending:$GROUP_ID" 2>/dev/null || echo 'none')s"
    fi
}

# Generate test images with different timestamps
generate_test_images() {
    local scenario=$1
    local count=$2
    
    echo -e "${YELLOW}📸 Generating test images for scenario: $scenario...${NC}"
    
    case $scenario in
        "burst")
            # All photos from same time period (should cluster into 1 meeting)
            for i in $(seq 1 $count); do
                timestamp=$(date -d "2024-01-01 10:00:00 +${i} minutes" '+%Y:%m:%d %H:%M:%S')
                create_test_image "$i" "$timestamp" "burst"
            done
            ;;
        "past")
            # Photos from different dates (should create separate meetings)
            for i in $(seq 1 $count); do
                timestamp=$(date -d "2024-01-0${i} 10:00:00" '+%Y:%m:%d %H:%M:%S')
                create_test_image "$i" "$timestamp" "past"
            done
            ;;
        "mixed")
            # Mix of same-day and different-day photos
            for i in $(seq 1 $count); do
                if [[ $((i % 3)) -eq 0 ]]; then
                    timestamp=$(date -d "2024-01-02 10:0${i}:00" '+%Y:%m:%d %H:%M:%S')
                else
                    timestamp=$(date -d "2024-01-01 10:0${i}:00" '+%Y:%m:%d %H:%M:%S')
                fi
                create_test_image "$i" "$timestamp" "mixed"
            done
            ;;
    esac
}

create_test_image() {
    local num=$1
    local timestamp=$2
    local scenario=$3
    
    if command -v convert &> /dev/null; then
        convert -size 800x600 "xc:lightblue" \
                -pointsize 40 \
                -draw "text 50,100 'Test Photo ${num}'" \
                -draw "text 50,150 'Time: ${timestamp}'" \
                -draw "text 50,200 'Scenario: ${scenario}'" \
                "$TEST_DIR/photo_${scenario}_${num}.jpg"
    else
        # Create dummy file
        echo -e "\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB\x00C\x00" > "$TEST_DIR/photo_${scenario}_${num}.jpg"
        echo "Test Photo $num - $timestamp - $scenario" >> "$TEST_DIR/photo_${scenario}_${num}.jpg"
    fi
}

# Function to upload a single photo
upload_photo() {
    local photo_path=$1
    local photo_name=$(basename "$photo_path")
    
    echo -e "${BLUE}📤 Uploading $photo_name...${NC}"
    
    response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Authorization: Bearer $JWT_TOKEN" \
        -F "file=@$photo_path" \
        -F "group_id=$GROUP_ID" \
        "$API_BASE_URL/photos/upload")
    
    http_code=$(echo "$response" | tail -n1)
    response_body=$(echo "$response" | head -n -1)
    
    if [[ "$http_code" == "200" ]]; then
        echo -e "${GREEN}✅ $photo_name uploaded successfully${NC}"
        return 0
    else
        echo -e "${RED}❌ $photo_name upload failed (HTTP $http_code)${NC}"
        echo "Response: $response_body"
        return 1
    fi
}

# Run test scenario
run_scenario() {
    local scenario=$1
    echo -e "${YELLOW}🔥 Running scenario: $scenario${NC}"
    
    generate_test_images "$scenario" "$PHOTO_COUNT"
    
    echo -e "${BLUE}📊 Initial Redis state:${NC}"
    monitor_redis_keys
    
    # Upload photos in burst
    start_time=$(date +%s)
    failed_uploads=0
    
    for photo_file in "$TEST_DIR"/photo_${scenario}_*.jpg; do
        if ! upload_photo "$photo_file"; then
            ((failed_uploads++))
        fi
        
        # Add delay between uploads
        if [[ "$UPLOAD_DELAY" != "0" ]]; then
            sleep "$UPLOAD_DELAY"
        fi
        
        # Monitor Redis keys periodically
        if [[ $((RANDOM % 5)) -eq 0 ]]; then
            monitor_redis_keys
        fi
    done
    
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    
    echo "================================================"
    echo -e "${BLUE}📊 Scenario '$scenario' Summary${NC}"
    echo "Total photos: $PHOTO_COUNT"
    echo "Failed uploads: $failed_uploads"
    echo "Successful uploads: $((PHOTO_COUNT - failed_uploads))"
    echo "Total duration: ${duration}s"
    echo "Average upload rate: $(echo "scale=2; $PHOTO_COUNT / $duration" | bc -l) photos/sec"
    echo "================================================"
    
    # Monitor final Redis state
    echo -e "${BLUE}📊 Final Redis state:${NC}"
    monitor_redis_keys
}

# Main test execution
main() {
    echo -e "${YELLOW}🧪 Starting enhanced clustering tests...${NC}"
    
    # Run specified scenarios
    IFS=',' read -ra SCENARIOS <<< "$TEST_SCENARIOS"
    for scenario in "${SCENARIOS[@]}"; do
        run_scenario "$scenario"
        
        # Wait between scenarios
        if [[ ${#SCENARIOS[@]} -gt 1 ]]; then
            echo -e "${YELLOW}⏳ Waiting 10 seconds before next scenario...${NC}"
            sleep 10
        fi
    done
    
    # Wait for clustering to complete
    echo -e "${YELLOW}⏳ Waiting for clustering to complete...${NC}"
    echo "This may take 5-15 seconds depending on CLUSTER_DEBOUNCE_TTL and CLUSTER_RETRY_DELAY settings"
    
    sleep_time=$((${CLUSTER_DEBOUNCE_TTL:-5} + ${CLUSTER_RETRY_DELAY:-3} + 5))
    echo "Sleeping for ${sleep_time} seconds..."
    
    for i in $(seq 1 $sleep_time); do
        echo -n "."
        sleep 1
        if [[ $((i % 10)) -eq 0 ]]; then
            echo ""
            monitor_redis_keys
        fi
    done
    echo ""
    
    # Final check
    echo -e "${BLUE}🔍 Final clustering results:${NC}"
    monitor_redis_keys
    
    echo -e "${GREEN}🎉 Enhanced test completed!${NC}"
    echo ""
    echo -e "${BLUE}Expected behavior by scenario:${NC}"
    echo "- burst: All photos should be in 1 meeting"
    echo "- past: Photos should be in separate meetings by date"  
    echo "- mixed: Photos should be grouped optimally"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Check worker logs for clustering activity"
    echo "2. Query meetings API: GET $API_BASE_URL/api/meetings?group_id=$GROUP_ID"
    echo "3. Verify Redis keys are cleaned up"
    echo "4. Check Prometheus/StatsD metrics if enabled"
}

# Cleanup function
cleanup() {
    echo -e "${YELLOW}🧹 Cleaning up test files...${NC}"
    rm -rf "$TEST_DIR"
    echo -e "${GREEN}✅ Cleanup complete${NC}"
}

# Trap cleanup on exit
trap cleanup EXIT

# Run main test
main 