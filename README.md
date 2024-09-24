# SID-Tools
Some tools for service id

## How to use 
### Prerequisites
### flow.logs file
In the router save the flow logs into one file using the following command
```bash
cd /data/lxc/fsam/rootfs/crsp/log
tail -F flow.log flow.log.1 | tee /mnt/sda1/flow.logs
```
After finishing collecting flow logs copy the file to your computer and save him in this dir

### classification defs file
There are 2 options. 
- You can put in this dir a classifiction def file and the script will use this file
- The other option is the script use the file that exist in staging

### installing requirements
```bash
pip install -r requirements.txt
```

## Analyze
When you have both files, classification_defs.json and flow.logs you can run the script using the command
```bash
python3 buckets_data_sum.py -lfp flow.logs -cfp classification_defs.json
```
