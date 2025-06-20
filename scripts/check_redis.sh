#!/bin/bash

# ================================
# 🔍 Redis Clustering Status Monitor
# ================================
# Real-time monitoring of Redis keys and clustering activity

set -e

# Configuration
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_DB="${REDIS_DB:-0}"
WATCH_INTERVAL="${WATCH_INTERVAL:-2}"
GROUP_ID="${GROUP_ID:-}"

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
    echo -e "${BLUE}║               🔍 Redis Clustering Monitor                ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo -e "${CYAN}Redis: ${REDIS_HOST}:${REDIS_PORT} (DB:${REDIS_DB})${NC}"
    echo -e "${CYAN}Time: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo ""
}

# Check Redis connection
check_redis_connection() {
    if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" ping > /dev/null 2>&1; then
        echo -e "${RED}❌ Cannot connect to Redis at ${REDIS_HOST}:${REDIS_PORT}${NC}"
        exit 1
    fi
}

# Get all clustering keys
get_clustering_keys() {
    local pattern="$1"
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" keys "$pattern" 2>/dev/null | sort
}

# Get key value with TTL
get_key_info() {
    local key="$1"
    local value=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" get "$key" 2>/dev/null || echo "")
    local ttl=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" ttl "$key" 2>/dev/null || echo "-1")
    local exists=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" exists "$key" 2>/dev/null || echo "0")
    
    if [[ "$exists" == "1" ]]; then
        if [[ "$ttl" == "-1" ]]; then
            echo "${value} (no TTL)"
        elif [[ "$ttl" == "-2" ]]; then
            echo "(expired)"
        else
            echo "${value} (TTL: ${ttl}s)"
        fi
    else
        echo "(not found)"
    fi
}

# Display clustering status
show_clustering_status() {
    echo -e "${YELLOW}📊 CLUSTERING KEYS OVERVIEW${NC}"
    echo "════════════════════════════════════════"
    
    # Get all clustering keys
    local pending_keys=($(get_clustering_keys "cluster:pending:*"))
    local job_keys=($(get_clustering_keys "cluster:job:*"))
    local count_keys=($(get_clustering_keys "cluster:count:*"))
    
    echo -e "${PURPLE}Pending Keys (${#pending_keys[@]}):${NC}"
    if [[ ${#pending_keys[@]} -eq 0 ]]; then
        echo "  (none)"
    else
        for key in "${pending_keys[@]}"; do
            local group_id=$(echo "$key" | cut -d: -f3)
            local info=$(get_key_info "$key")
            echo -e "  ${GREEN}${group_id}${NC}: $info"
        done
    fi
    
    echo ""
    echo -e "${PURPLE}Job Keys (${#job_keys[@]}):${NC}"
    if [[ ${#job_keys[@]} -eq 0 ]]; then
        echo "  (none)"
    else
        for key in "${job_keys[@]}"; do
            local group_id=$(echo "$key" | cut -d: -f3)
            local info=$(get_key_info "$key")
            echo -e "  ${YELLOW}${group_id}${NC}: $info"
        done
    fi
    
    echo ""
    echo -e "${PURPLE}Count Keys (${#count_keys[@]}):${NC}"
    if [[ ${#count_keys[@]} -eq 0 ]]; then
        echo "  (none)"
    else
        for key in "${count_keys[@]}"; do
            local group_id=$(echo "$key" | cut -d: -f3)
            local info=$(get_key_info "$key")
            echo -e "  ${CYAN}${group_id}${NC}: $info"
        done
    fi
}

# Show specific group status
show_group_status() {
    local gid="$1"
    
    echo ""
    echo -e "${YELLOW}🎯 GROUP SPECIFIC STATUS: ${gid}${NC}"
    echo "════════════════════════════════════════"
    
    local pending_key="cluster:pending:${gid}"
    local job_key="cluster:job:${gid}"
    local count_key="cluster:count:${gid}"
    
    echo -e "${PURPLE}Pending:${NC} $(get_key_info "$pending_key")"
    echo -e "${PURPLE}Job:${NC}     $(get_key_info "$job_key")"
    echo -e "${PURPLE}Count:${NC}   $(get_key_info "$count_key")"
    
    # Additional info
    local pending_exists=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" exists "$pending_key")
    local job_exists=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" exists "$job_key")
    
    echo ""
    if [[ "$pending_exists" == "1" && "$job_exists" == "1" ]]; then
        echo -e "${YELLOW}⏳ Status: Uploads in progress, clustering scheduled${NC}"
    elif [[ "$pending_exists" == "1" && "$job_exists" == "0" ]]; then
        echo -e "${RED}⚠️  Status: Uploads detected but no job scheduled (potential issue)${NC}"
    elif [[ "$pending_exists" == "0" && "$job_exists" == "1" ]]; then
        echo -e "${GREEN}🔄 Status: Group quiet, clustering may be running${NC}"
    else
        echo -e "${GREEN}✅ Status: Group quiet, no clustering activity${NC}"
    fi
}

# Show Redis general info
show_redis_info() {
    echo ""
    echo -e "${YELLOW}🔧 REDIS SYSTEM INFO${NC}"
    echo "════════════════════════════════════════"
    
    local info=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" info replication 2>/dev/null)
    local memory=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" info memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
    local keys=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" dbsize 2>/dev/null)
    local uptime=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" info server | grep uptime_in_seconds | cut -d: -f2 | tr -d '\r')
    
    echo -e "${PURPLE}Memory Usage:${NC} $memory"
    echo -e "${PURPLE}Total Keys:${NC} $keys"
    echo -e "${PURPLE}Uptime:${NC} $((uptime / 3600))h $((uptime % 3600 / 60))m $((uptime % 60))s"
}

# Cleanup stale keys
cleanup_stale_keys() {
    echo -e "${YELLOW}🧹 Cleaning up stale keys...${NC}"
    
    local cleaned=0
    local job_keys=($(get_clustering_keys "cluster:job:*"))
    
    for job_key in "${job_keys[@]}"; do
        local group_id=$(echo "$job_key" | cut -d: -f3)
        local pending_key="cluster:pending:${group_id}"
        local job_ttl=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" ttl "$job_key")
        
        # If job key exists but no pending key, and TTL is high, it might be stale
        if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" exists "$pending_key" > /dev/null; then
            if [[ "$job_ttl" -gt 60 ]]; then  # More than 1 minute
                redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" del "$job_key" > /dev/null
                echo -e "${GREEN}Cleaned stale job key: ${job_key}${NC}"
                ((cleaned++))
            fi
        fi
    done
    
    if [[ $cleaned -eq 0 ]]; then
        echo -e "${GREEN}No stale keys found${NC}"
    else
        echo -e "${GREEN}Cleaned $cleaned stale keys${NC}"
    fi
}

# Interactive mode
interactive_mode() {
    echo -e "${CYAN}Interactive mode. Commands:${NC}"
    echo "  q/quit - Exit"
    echo "  c/clean - Clean stale keys"
    echo "  r/refresh - Refresh display"
    echo "  g <group_id> - Show specific group status"
    echo ""
    
    while true; do
        print_header
        show_clustering_status
        
        if [[ -n "$GROUP_ID" ]]; then
            show_group_status "$GROUP_ID"
        fi
        
        show_redis_info
        
        echo ""
        echo -e "${CYAN}Commands: q(uit), c(lean), r(efresh), g <group_id>${NC}"
        echo -n "Enter command (or wait ${WATCH_INTERVAL}s for auto-refresh): "
        
        read -t "$WATCH_INTERVAL" cmd args || continue
        
        case "$cmd" in
            q|quit)
                echo "Exiting..."
                exit 0
                ;;
            c|clean)
                cleanup_stale_keys
                sleep 2
                ;;
            r|refresh)
                continue
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

# Watch mode (auto-refresh)
watch_mode() {
    while true; do
        print_header
        show_clustering_status
        
        if [[ -n "$GROUP_ID" ]]; then
            show_group_status "$GROUP_ID"
        fi
        
        show_redis_info
        
        echo ""
        echo -e "${CYAN}Auto-refreshing every ${WATCH_INTERVAL}s (Ctrl+C to exit)${NC}"
        sleep "$WATCH_INTERVAL"
    done
}

# Single run mode
single_run() {
    print_header
    show_clustering_status
    
    if [[ -n "$GROUP_ID" ]]; then
        show_group_status "$GROUP_ID"
    fi
    
    show_redis_info
}

# Help
show_help() {
    echo "Redis Clustering Monitor"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help"
    echo "  -w, --watch             Watch mode (auto-refresh)"
    echo "  -i, --interactive       Interactive mode"
    echo "  -g, --group GROUP_ID    Monitor specific group"
    echo "  -c, --clean             Clean stale keys and exit"
    echo "  --host HOST             Redis host (default: localhost)"
    echo "  --port PORT             Redis port (default: 6379)"
    echo "  --db DB                 Redis database (default: 0)"
    echo "  --interval SECONDS      Refresh interval (default: 2)"
    echo ""
    echo "Environment Variables:"
    echo "  REDIS_HOST              Redis host"
    echo "  REDIS_PORT              Redis port"
    echo "  REDIS_DB                Redis database"
    echo "  WATCH_INTERVAL          Refresh interval"
    echo "  GROUP_ID                Group to monitor"
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
            -c|--clean)
                mode="clean"
                shift
                ;;
            --host)
                REDIS_HOST="$2"
                shift 2
                ;;
            --port)
                REDIS_PORT="$2"
                shift 2
                ;;
            --db)
                REDIS_DB="$2"
                shift 2
                ;;
            --interval)
                WATCH_INTERVAL="$2"
                shift 2
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Check Redis connection
    echo -e "${BLUE}Checking Redis connection...${NC}"
    check_redis_connection
    echo -e "${GREEN}✅ Connected to Redis${NC}"
    sleep 1
    
    case "$mode" in
        watch)
            watch_mode
            ;;
        interactive)
            interactive_mode
            ;;
        clean)
            cleanup_stale_keys
            ;;
        single)
            single_run
            ;;
    esac
}

# Check dependencies
if ! command -v redis-cli &> /dev/null; then
    echo -e "${RED}❌ redis-cli not found. Please install redis-tools${NC}"
    echo "Ubuntu/Debian: sudo apt install redis-tools"
    echo "CentOS/RHEL: sudo yum install redis"
    exit 1
fi

main "$@" 