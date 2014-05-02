__author__ = 'Aditya Laghate'

import sys
import os
import socket
import paramiko
import time
import logging
from boto.ec2 import connect_to_region
from boto.exception import EC2ResponseError
from config import *


logger = logging.getLogger(__name__)


def create_sec_group(connection):
    try:
        sec = connection.create_security_group(
            name=sec_group['name'],
            description=sec_group['description']
        )

        sec.authorize(ip_protocol='tcp',
                      from_port=22,
                      to_port=22,
                      cidr_ip='0.0.0.0/0'
                      )

        sec.authorize(ip_protocol='tcp',
                      from_port=28017,
                      to_port=28017,
                      cidr_ip='0.0.0.0/0')

        sec.authorize(src_group=sec)

        logger.info('Security group created: %s' % sec.name)

        return sec

    except EC2ResponseError, err:
        if err.error_code == 'InvalidGroup.Duplicate':
            for sec in connection.get_all_security_groups():
                if sec.name == sec_group['name']:
                    logger.info('Using existing security group: %s' % sec.name)
                    return sec
    except Exception, err:
        logger.critical("Error: %s" % err)
        raise err


def launch_instances(connection, sec, key_name):
    try:
        reservations = []
        user_data = open('user_data.sh', 'r').read()
        for i in range(replica_sets['count']):
            if not replica_sets['name_prefix'] == '':
                rpl_set_name = ('%s_%s' % (replica_sets['name_prefix'], i + 1))
                rpl_data = user_data + \
                    '\necho replSet=%s | sudo tee -a /etc/mongodb.conf \nsudo init 6'% rpl_set_name
            else:
                rpl_set_name = ''
                rpl_data = user_data + '\nsudo init 6'

            reservation = connection.run_instances(
                image_id=instance_details['ami'],
                min_count=replica_sets['instances_per_set'],
                max_count=replica_sets['instances_per_set'],
                key_name=key_name,
                security_groups=[sec.name],
                instance_type=instance_details['type'],
                user_data=rpl_data
            )

            for instance in reservation.instances:
                while instance.state != 'running':
                    time.sleep(5)
                    instance.update()

            for j, instance in enumerate(reservation.instances):
                _name = '%s_db_server_%s' % (rpl_set_name, j + 1)
                instance.add_tag(key='Name',
                                 value=_name)
                instance.add_tag(key='Owner',
                                 value=__author__)

                time.sleep(0.25)

                logger.info('Instance created: %s in replica set %s' %
                            (instance.id, rpl_set_name)
                            )
                logger.info('%s : %s' % (_name, instance.public_dns_name))
                logger.info('%s : %s' % (_name, instance.private_ip_address))

            reservations.append({'rpl_set': rpl_set_name,
                                 'reservation': reservation})

        return reservations

    except Exception as err:
        logger.critical("Error: %s" % err)
        raise err


def provision_ebs_volumes(connection, reservations):
    try:
        for reservation in reservations:
            for instance in reservation['reservation'].instances:
                for i in range(volume_details['number']):
                    ebs_volume = connection.create_volume(
                        size=volume_details['size'],
                        zone=instance.placement,
                        volume_type='standard',
                        iops=None
                    )

                    while ebs_volume.status != 'available':
                        time.sleep(5)
                        ebs_volume.update()

                    ebs_volume.add_tag(key='Name',
                                       value='%s_Disk_%s_%s' % (reservation['rpl_set'], i + 1, instance.id))

                    ebs_volume.attach(instance_id=instance.id,
                                      device='/dev/sdh%i' % (i + 1))
                    logger.info('%s attached to %s' % (ebs_volume.id, instance.id))

        return 'Done'
    except Exception as err:
        logger.critical("Error: %s" % err)
        raise err


def _wait_for_ssh(host, key_filename):
    retries = 10
    while True:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        tic = time.time()
        try:
            client.connect(hostname=host, username='ubuntu', key_filename=key_filename, timeout=30)
        except (socket.error, EOFError), err:
            logger.info('SSH error: %s' % err)
            toc = time.time()
            diff = toc - tic
            if diff < 30:
                time.sleep(30 - diff)
            retries -= 1
            if retries == 0:
                logger.critical('ssh timed out to host %s' % host)
                sys.exit(1)
            else:
                logger.debug('ssh connected')
                continue
        else:
            return
        finally:
            client.close()


def check_key(conn, key_name):
    key_found = False
    keys = conn.get_all_key_pairs()
    for key in keys:
        if key.name == key_name:
            key_found = True
            logger.info('Using a SSH key: %s' % key.name)
            break

    if not key_found:
        key = conn.create_key_pair('%s-%s' % (conn.region.name, key_name))
        key.save(os.path.abspath('.'))
        logger.info('SSH key created: %s' % key.name)

    return key.name

if __name__ == "__main__":
    logging.basicConfig(filename="ec2_deploy.log", level=logging.DEBUG, filemode='w')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    logging.getLogger('paramiko').setLevel(logging.CRITICAL)

    conn = connect_to_region(region_name=region_details['region'],
                             aws_access_key_id=ec2_creds['access_key'],
                             aws_secret_access_key=ec2_creds['secret_key'])

    key = check_key(conn, region_details['key_name'])
    sec_group = create_sec_group(conn)
    reservations = launch_instances(conn, sec_group, key)
    status = provision_ebs_volumes(conn, reservations)
    logger.info("Replicated & sharded clusters setup, please configure them.")