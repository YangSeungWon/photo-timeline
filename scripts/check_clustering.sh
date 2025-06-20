#!/bin/bash

# ================================
# 📊 Clustering Status Monitor
# ================================
# Monitor database meetings, worker status, and clustering health

set -e

# Configuration
API_BASE_URL="${API_BASE_URL:-http://localhost:3067/api/v1}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-phototimeline}"
POSTGRES_USER="${POSTGRES_USER:-user}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-password}"
GROUP_ID="${GROUP_ID:-}"
JWT_TOKEN="${JWT_TOKEN:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Header
print_header() {
    clear
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║              📊 Clustering Status Monitor               ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo -e "${CYAN}Time: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo ""
}

# Check database connection
check_database() {
    if command -v psql &> /dev/null; then
        echo -e "${BLUE}🔍 Checking database connection...${NC}"
        if PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Database connected${NC}"
            return 0
        else
            echo -e "${RED}❌ Cannot connect to database${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️  psql not found, skipping database checks${NC}"
        return 1
    fi
}

# Get database statistics
get_db_stats() {
    if ! check_database; then
        return 1
    fi
    
    echo -e "${YELLOW}📊 DATABASE STATISTICS${NC}"
    echo "════════════════════════════════════════"
    
    # Get meeting and photo counts
    local stats=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "
        SELECT 
            COUNT(DISTINCT m.id) as meeting_count,
            COUNT(DISTINCT p.id) as photo_count,
            COUNT(DISTINCT g.id) as group_count,
            COUNT(DISTINCT u.id) as user_count
        FROM meetings m
        FULL OUTER JOIN photos p ON m.id = p.meeting_id
        FULL OUTER JOIN groups g ON m.group_id = g.id
        FULL OUTER JOIN users u ON p.uploader_id = u.id;
    " 2>/dev/null)
    
    if [[ -n "$stats" ]]; then
        local meeting_count=$(echo "$stats" | tr -d ' ' | cut -d'|' -f1)
        local photo_count=$(echo "$stats" | tr -d ' ' | cut -d'|' -f2)
        local group_count=$(echo "$stats" | tr -d ' ' | cut -d'|' -f3)
        local user_count=$(echo "$stats" | tr -d ' ' | cut -d'|' -f4)
        
        echo -e "${PURPLE}Total Meetings:${NC} $meeting_count"
        echo -e "${PURPLE}Total Photos:${NC} $photo_count"
        echo -e "${PURPLE}Total Groups:${NC} $group_count"
        echo -e "${PURPLE}Total Users:${NC} $user_count"
    fi
}

# Get group-specific statistics
get_group_stats() {
    local gid="$1"
    
    if ! check_database; then
        return 1
    fi
    
    echo ""
    echo -e "${YELLOW}🎯 GROUP STATISTICS: ${gid}${NC}"
    echo "════════════════════════════════════════"
    
    # Get detailed group stats
    local group_stats=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "
        SELECT 
            COUNT(DISTINCT m.id) as meeting_count,
            COUNT(DISTINCT p.id) as photo_count,
            COUNT(DISTINCT CASE WHEN m.title = 'Default Meeting' THEN m.id END) as default_meetings,
            COUNT(DISTINCT CASE WHEN m.title != 'Default Meeting' THEN m.id END) as auto_meetings,
            COUNT(DISTINCT CASE WHEN m.title = 'Default Meeting' THEN p.id END) as default_photos,
            COUNT(DISTINCT CASE WHEN m.title != 'Default Meeting' THEN p.id END) as clustered_photos
        FROM meetings m
        FULL OUTER JOIN photos p ON m.id = p.meeting_id
        WHERE m.group_id = '$gid' OR p.group_id = '$gid';
    " 2>/dev/null)
    
    if [[ -n "$group_stats" ]]; then
        local meeting_count=$(echo "$group_stats" | tr -d ' ' | cut -d'|' -f1)
        local photo_count=$(echo "$group_stats" | tr -d ' ' | cut -d'|' -f2)
        local default_meetings=$(echo "$group_stats" | tr -d ' ' | cut -d'|' -f3)
        local auto_meetings=$(echo "$group_stats" | tr -d ' ' | cut -d'|' -f4)
        local default_photos=$(echo "$group_stats" | tr -d ' ' | cut -d'|' -f5)
        local clustered_photos=$(echo "$group_stats" | tr -d ' ' | cut -d'|' -f6)
        
        echo -e "${PURPLE}Meetings:${NC} $meeting_count (Default: $default_meetings, Auto: $auto_meetings)"
        echo -e "${PURPLE}Photos:${NC} $photo_count (Default: $default_photos, Clustered: $clustered_photos)"
        
        # Calculate clustering efficiency
        if [[ "$photo_count" -gt 0 ]]; then
            local efficiency=$(echo "scale=1; $clustered_photos * 100 / $photo_count" | bc -l 2>/dev/null || echo "0")
            echo -e "${PURPLE}Clustering Efficiency:${NC} ${efficiency}%"
        fi
    fi
    
    # Show recent meetings
    echo ""
    echo -e "${CYAN}📅 Recent Meetings:${NC}"
    PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
        SELECT 
            LEFT(title, 30) as title,
            photo_count,
            meeting_date,
            TO_CHAR(created_at, 'MM-DD HH24:MI') as created
        FROM meetings 
        WHERE group_id = '$gid' 
        ORDER BY created_at DESC 
        LIMIT 10;
    " 2>/dev/null || echo "Could not fetch meeting data"
}

# Get worker status
get_worker_status() {
    echo ""
    echo -e "${YELLOW}⚙️  WORKER STATUS${NC}"
    echo "════════════════════════════════════════"
    
    # Check if Docker worker is running
    local docker_status=$(docker compose ps worker 2>/dev/null | grep -q "Up" && echo "running" || echo "stopped")
    echo -e "${PURPLE}Docker Worker:${NC} $docker_status"
    
    # Check RQ worker status via Redis
    if command -v redis-cli &> /dev/null; then
        local worker_count=$(redis-cli -h localhost -p 6379 keys "rq:worker:*" 2>/dev/null | wc -l)
        echo -e "${PURPLE}Active RQ Workers:${NC} $worker_count"
        
        # Check job queues
        local default_queue=$(redis-cli -h localhost -p 6379 llen "rq:queue:default" 2>/dev/null || echo "0")
        local failed_queue=$(redis-cli -h localhost -p 6379 llen "rq:queue:failed" 2>/dev/null || echo "0")
        
        echo -e "${PURPLE}Pending Jobs:${NC} $default_queue"
        echo -e "${PURPLE}Failed Jobs:${NC} $failed_queue"
        
        if [[ "$failed_queue" -gt 0 ]]; then
            echo -e "${RED}⚠️  Warning: $failed_queue failed jobs detected${NC}"
        fi
    fi
}

# Check API health
check_api_health() {
    echo ""
    echo -e "${YELLOW}🌐 API STATUS${NC}"  
    echo "════════════════════════════════════════"
    
    # Check health endpoint
    local health_response=$(curl -s "$API_BASE_URL/../health" 2>/dev/null)
    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✅ API is responding${NC}"
        echo "$health_response" | jq . 2>/dev/null || echo "$health_response"
    else
        echo -e "${RED}❌ API not responding${NC}"
    fi
    
    # Check if JWT token is provided and valid
    if [[ -n "$JWT_TOKEN" ]]; then
        local auth_check=$(curl -s -H "Authorization: Bearer $JWT_TOKEN" "$API_BASE_URL/auth/me" 2>/dev/null)
        if [[ $? -eq 0 ]]; then
            echo -e "${GREEN}✅ JWT token is valid${NC}"
        else
            echo -e "${YELLOW}⚠️  JWT token validation failed${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  No JWT token provided${NC}"
    fi
}

# Get clustering configuration
get_clustering_config() {
    echo ""
    echo -e "${YELLOW}⚙️  CLUSTERING CONFIGURATION${NC}"
    echo "════════════════════════════════════════"
    
    # Try to get config from environment or defaults
    local meeting_gap=${MEETING_GAP_HOURS:-24}
    local debounce_ttl=${CLUSTER_DEBOUNCE_TTL:-5}
    local retry_delay=${CLUSTER_RETRY_DELAY:-3}
    local max_retries=${CLUSTER_MAX_RETRIES:-2}
    
    echo -e "${PURPLE}Meeting Gap:${NC} ${meeting_gap} hours"
    echo -e "${PURPLE}Debounce TTL:${NC} ${debounce_ttl} seconds"
    echo -e "${PURPLE}Retry Delay:${NC} ${retry_delay} seconds"
    echo -e "${PURPLE}Max Retries:${NC} ${max_retries}"
}

# System health check
run_health_check() {
    echo -e "${YELLOW}🔍 SYSTEM HEALTH CHECK${NC}"
    echo "════════════════════════════════════════"
    
    local issues=0
    
    # Check Docker services
    if ! docker compose ps | grep -q "Up"; then
        echo -e "${RED}❌ Some Docker services are not running${NC}"
        ((issues++))
    else
        echo -e "${GREEN}✅ Docker services are running${NC}"
    fi
    
    # Check database
    if ! check_database; then
        echo -e "${RED}❌ Database connection failed${NC}"
        ((issues++))
    else
        echo -e "${GREEN}✅ Database is accessible${NC}"
    fi
    
    # Check Redis
    if ! redis-cli ping > /dev/null 2>&1; then
        echo -e "${RED}❌ Redis connection failed${NC}"
        ((issues++))
    else
        echo -e "${GREEN}✅ Redis is accessible${NC}"
    fi
    
    # Check API
    if ! curl -s "$API_BASE_URL/../health" > /dev/null; then
        echo -e "${RED}❌ API is not responding${NC}"
        ((issues++))
    else
        echo -e "${GREEN}✅ API is responding${NC}"
    fi
    
    echo ""
    if [[ $issues -eq 0 ]]; then
        echo -e "${GREEN}🎉 All systems are healthy!${NC}"
    else
        echo -e "${RED}⚠️  Found $issues issues${NC}"
    fi
    
    return $issues
}

# Interactive mode
interactive_mode() {
    while true; do
        print_header
        run_health_check
        get_db_stats
        get_worker_status
        check_api_health
        get_clustering_config
        
        if [[ -n "$GROUP_ID" ]]; then
            get_group_stats "$GROUP_ID"
        fi
        
        echo ""
        echo -e "${CYAN}Commands: q(uit), h(ealth), g <group_id>, r(efresh)${NC}"
        echo -n "Enter command (or wait 5s for auto-refresh): "
        
        read -t 5 cmd args || continue
        
        case "$cmd" in
            q|quit)
                echo "Exiting..."
                exit 0
                ;;
            h|health)
                run_health_check
                sleep 3
                ;;
            g)
                if [[ -n "$args" ]]; then
                    GROUP_ID="$args"
                    echo -e "${GREEN}Switched to group: $GROUP_ID${NC}"
                    sleep 1
                else
                    echo -e "${RED}Usage: g <group_id>${NC}"
                    sleep 2
                fi
                ;;
            r|refresh)
                continue
                ;;
            "")
                continue
                ;;
            *)
                echo -e "${RED}Unknown command: $cmd${NC}"
                sleep 1
                ;;
        esac
    done
}

# Watch mode
watch_mode() {
    while true; do
        print_header
        run_health_check
        get_db_stats
        get_worker_status
        check_api_health
        
        if [[ -n "$GROUP_ID" ]]; then
            get_group_stats "$GROUP_ID"
        fi
        
        echo ""
        echo -e "${CYAN}Auto-refreshing every 5s (Ctrl+C to exit)${NC}"
        sleep 5
    done
}

# Single run
single_run() {
    print_header
    run_health_check
    get_db_stats
    get_worker_status
    check_api_health
    get_clustering_config
    
    if [[ -n "$GROUP_ID" ]]; then
        get_group_stats "$GROUP_ID"
    fi
}

# Help
show_help() {
    echo "Clustering Status Monitor"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help"
    echo "  -w, --watch             Watch mode (auto-refresh)"
    echo "  -i, --interactive       Interactive mode"
    echo "  -g, --group GROUP_ID    Monitor specific group"
    echo "  --health                Run health check only"
    echo "  --api-url URL           API base URL"
    echo "  --db-host HOST          Database host"
    echo "  --db-port PORT          Database port"
    echo "  --db-name NAME          Database name"
    echo "  --db-user USER          Database user"
    echo "  --db-password PASS      Database password"
    echo ""
    echo "Environment Variables:"
    echo "  API_BASE_URL            API base URL"
    echo "  POSTGRES_HOST           Database host"
    echo "  POSTGRES_PORT           Database port"
    echo "  POSTGRES_DB             Database name"
    echo "  POSTGRES_USER           Database user"
    echo "  POSTGRES_PASSWORD       Database password"
    echo "  GROUP_ID                Group to monitor"
    echo "  JWT_TOKEN               Authentication token"
}

# Main
main() {
    local mode="single"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -w|--watch)
                mode="watch"
                shift
                ;;
            -i|--interactive)
                mode="interactive"
                shift
                ;;
            -g|--group)
                GROUP_ID="$2"
                shift 2
                ;;
            --health)
                mode="health"
                shift
                ;;
            --api-url)
                API_BASE_URL="$2"
                shift 2
                ;;
            --db-host)
                POSTGRES_HOST="$2"
                shift 2
                ;;
            --db-port)
                POSTGRES_PORT="$2"
                shift 2
                ;;
            --db-name)
                POSTGRES_DB="$2"
                shift 2
                ;;
            --db-user)
                POSTGRES_USER="$2"
                shift 2
                ;;
            --db-password)
                POSTGRES_PASSWORD="$2"
                shift 2
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    case "$mode" in
        watch)
            watch_mode
            ;;
        interactive)
            interactive_mode
            ;;
        health)
            run_health_check
            ;;
        single)
            single_run
            ;;
    esac
}

# Check dependencies
if ! command -v curl &> /dev/null; then
    echo -e "${RED}❌ curl not found. Please install curl${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}⚠️  docker not found. Docker status checks will be skipped${NC}"
fi

main "$@" 