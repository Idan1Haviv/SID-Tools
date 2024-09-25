#!/bin/bash 

LOG_FILE="/crsp/log/flow.log"
LOG_ONE_FILE="/crsp/log/flow.log.1"

services_id_file="sam/services_id.jsonl"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color


process_line(){
    local line="$1"
    
    date=$(echo "$line" | awk '{print $2}')
    hour=$(echo "$line" | awk '{print $3}')
    domain_or_ip=$(echo "$line" | awk '{print $7}')
    service_id=$(echo "$line" | awk '{print $10}' | tr -d ',')
    category=$(echo "$line" | awk '{print $12}' | tr -d ')')
    rx=$(echo "$line" | awk '{print $15}')
    tx=$(echo "$line" | awk '{print $17}')

    if [[ "$service_id" =~ ^[0-9]+$ ]] && ((service_id > 0 )); then
	echo "Service id: $service_id"
        service_name=$(jq --argjson sid "$service_id" 'select(.id == $sid) | .display_name' "$services_id_file")
	echo "Service Name: $service_name"
        echo -e "$date $hour - Inserting Domain: ${GREEN}$domain_or_ip${NC} - Service: ${GREEN}$service_name${NC} - Category: $category - RX: $rx - TX: $tx" 
    else
	echo "Service id: General"
        echo -e "$date $hour - Inserting Domain: ${RED}$domain_or_ip${NC} - Service: ${RED}$service_id${NC} - Category: $category - RX: $rx - TX: $tx" 
    fi
    echo
}


tail -F $LOG_FILE $LOG_ONE_FILE | while read line
do
    if [[ "$line" == *"update_net_usage"* && "$line" == *"Inserting"* ]]; then
        process_line "$line"
    fi
done
