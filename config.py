# Config file

# EC2 API credentials
ec2_creds = {
    'access_key': '',
    'secret_key': ''
}

# EC2 region details, viz. us-west-2, us-east-1, etc
# EC2 SSH key name
region_details = {
    'region': '',
    'key_name': ''
}

# Replica set configuration
# count: Number of replica sets (int)
# instances_per_set: Number of servers / replica set (int)
# name_prefix: Name prefix to use for the replica sets, eg. rs_1, rs_2

replica_sets = {
    'count': 3,
    'instances_per_set': 3,
    'name_prefix': ''
}

# Instance Details
# ami: AMI id to use to launch EC2 Instance, eg: ami-6aad335a
# type: Instance size, eg: m1.large, m1.small, etc.

instance_details = {
    'ami': '',
    'type': '',
}

# This script setups up MongoDB configuration files on an 
# EBS backed drives, which are setup in a RAID 10 configuration.
# number: Number of disks to use in RAID10 config, min. 4 required
# size: Size in GB / per disk
# mount_point: Mount point to use 

volume_details = {
    'number': 4,
    'size': 400,
    'mount_point': 'xvdh'
}

# Security Group
# If the named group does not exist, this script will create a sec group
# as required by MongoDB

sec_group = {
    'name': '',
    'description': '',
}
