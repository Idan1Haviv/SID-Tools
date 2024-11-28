#!/bin/bash

flow_log="/crsp/log/flow.log"
flow_log_one="/crsp/log/flow.log.1"
services_id_file="/sam/services_id.jsonl"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color


get_net_usage_threshold(){
  # getting net_usage_threshold from samdb
  echo $(grep usage /crsp/storage/samdb | awk -F "," '{print $4}' | awk '{print $NF}') | awk '{print $1}'
}


process_inserting(){
  line=$1
  # echo $line
  
  date=$(echo $line | awk '{print $2}')
  hour=$(echo $line | awk '{print $3}')
  domain_or_ip=$(echo $line | awk '{print $7}')
  service_id=$(echo $line | awk '{print $10}' | tr -d ',')
  category=$(echo $line | awk '{print $12}' | tr -d ')')
  rx=$(echo $line | awk '{print $15}')
  tx=$(echo $line | awk '{print $17}')
  
  if [[ $rx -ge $(get_net_usage_threshold) ]]; then
    #echo -e "${GREEN}Inserting:${NC} "
    #echo -e "Date: $date, Hour: $hour, Domain: ${GREEN}$domain_or_ip${NC}, Service ID: $service_id, Category: $category, Rx: $rx, Tx: $tx"
    #echo 

    if [[ "$service_id" =~ ^[0-9]+$ ]] && ((service_id > 0 )); then
	echo "Service id: $service_id"
        service_name=$(jq --argjson sid "$service_id" 'select(.id == $sid) | .display_name' "$services_id_file")
	echo "Service Name: $service_name"
        echo -e "$date $hour - Inserting Domain: ${GREEN}$domain_or_ip${NC} - Service: ${GREEN}$service_name${NC} - Category: $category - RX: $rx - TX: $tx" 
        echo
    else
	echo "Service id: General"
        echo -e "$date $hour - Inserting Domain: ${RED}$domain_or_ip${NC} - Service: ${RED}$service_id${NC} - Category: $category - RX: $rx - TX: $tx" 
        echo
    fi

  fi
}


process_wont_inserted(){
  line=$1
  # echo $line
  
  date=$(echo $line | awk '{print $2}')
  hour=$(echo $line | awk '{print $3}')
  domain_or_ip=$(echo $line | awk '{print $9}')
  service_id=$(echo $line | awk '{print $12}' | tr -d ',')
  category=$(echo $line | awk '{print $14}' | tr -d ')')
  rx=$(echo $line | awk '{print $17}')
  tx=$(echo $line | awk '{print $19}')
  
  if [[ $rx -ge $(get_net_usage_threshold) ]]; then
    #echo -e "${RED}Wont inserted:${NC} "
    #echo -e "Date: $date, Hour: $hour, Domain: ${RED}$domain_or_ip${NC}, Service ID: $service_id, Category: $category, Rx: $rx, Tx: $tx"
    #echo
    
    if [[ "$service_id" =~ ^[0-9]+$ ]] && ((service_id > 0 )); then
      echo "Service id: $service_id"
      service_name=$(jq --argjson sid "$service_id" 'select(.id == $sid) | .display_name' "$services_id_file")
      echo "Service Name: $service_name"
      echo -e "$date $hour - Won't be inserted Domain: ${RED}$domain_or_ip${NC} - Service: ${RED}$service_id${NC} - Category: $category - RX: $rx - TX: $tx" 
      echo
    fi    

  fi
}


run(){
  net_usage=$(get_net_usage_threshold)
  echo "Net usage threshold: $net_usage"

  tail -F $flow_log $flow_log_one | while read line
  do
    if [[ $line == *"send: "* ]]; then
      echo "$line" | jq

    elif [[ $line == *"update_net_usage"* ]] && [[ $line == *"Inserting"* ]]; then
      process_inserting "$line" 

    elif [[ $line == *"update_net_usage"* ]] && [[ $line == *"Won't be inserted"* ]]; then
      process_wont_inserted "$line"
    fi
    
  done
}

run
