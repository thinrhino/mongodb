#!/bin/bash
set -e -x
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 7F0CEB10
echo 'deb http://downloads-distro.mongodb.org/repo/ubuntu-upstart dist 10gen' | sudo tee /etc/apt/sources.list.d/mongodb.list

sudo DEBIAN_FRONTEND='noninteractive' apt-get update && sudo apt-get upgrade -y
sudo DEBIAN_FRONTEND='noninteractive' apt-get install -y mdadm lvm2

for x in {1..4}; do
    echo 'Waiting for disks to attach'
    while [ ! -d /sys/block/xvdh${x} ]; do sleep 5; done
done

sudo mdadm --verbose --create /dev/md0 --level=10 --chunk=256 --raid-devices=4 /dev/xvdh1 /dev/xvdh2 /dev/xvdh3 /dev/xvdh4
echo 'DEVICE /dev/xvdh1 /dev/xvdh2 /dev/xvdh3 /dev/xvdh4' | sudo tee -a /etc/mdadm.conf
sudo mdadm --detail --scan | sudo tee -a /etc/mdadm.conf

sudo blockdev --setra 128 /dev/md0

for x in {1..4}; do
    sudo blockdev --setra 128 /dev/xvdh${x};
done

sudo dd if=/dev/zero of=/dev/md0 bs=512 count=1
sudo pvcreate /dev/md0
sudo vgcreate vg0 /dev/md0

sudo lvcreate -l 50%vg -n data vg0
sudo lvcreate -l 25%vg -n log vg0
sudo lvcreate -l 25%vg -n journal vg0

sudo mke2fs -t ext4 -F /dev/vg0/data
sudo mke2fs -t ext4 -F /dev/vg0/log
sudo mke2fs -t ext4 -F /dev/vg0/journal

sudo mkdir /data
sudo mkdir /log
sudo mkdir /journal

echo '/dev/vg0/data /data ext4 defaults,auto,noatime,noexec 0 0' | sudo tee -a /etc/fstab
echo '/dev/vg0/log /log ext4 defaults,auto,noatime,noexec 0 0' | sudo tee -a /etc/fstab
echo '/dev/vg0/journal /journal ext4 defaults,auto,noatime,noexec 0 0' | sudo tee -a /etc/fstab

sudo mount /data
sudo mount /log
sudo mount /journal

sudo ln -s /journal /data/journal

sudo DEBIAN_FRONTEND='noninteractive' apt-get install -y mongodb-10gen

sudo chown mongodb:mongodb /data
sudo chown mongodb:mongodb /log
sudo chown mongodb:mongodb /journal

sudo sed -i '/logpath=/ s/=.*/=\/log\/mongodb.log/' /etc/mongodb.conf
sudo sed -i '/logappend=/ s/=.*/=true/' /etc/mongodb.conf
sudo sed -i '/dbpath=/ s/=.*/=\/data/' /etc/mongodb.conf
echo fork=true | sudo tee -a /etc/mongodb.conf
