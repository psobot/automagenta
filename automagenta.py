#!/usr/bin/env python

import os
import sys
import boto3
from termcolor import colored
from botocore.exceptions import ClientError
import getpass
import subprocess
import time

# Prereqs:
#  pip install boto3
#  brew install s3cmd

REGION = boto3.session.Session().region_name

USER_NAME = 'ec2-user'

USER_DATA = """
#!/bin/bash

# Shutdown as soon as we have no open SSH sessions,
# checking every 5 minutes after the first 50.
sleep 3000
echo "*/5 * * * * bash -c \"/bin/netstat -tnpa | /bin/grep 'ESTABLISHED.*sshd' || /sbin/shutdown -h now\"" > \
    /tmp/crontab.txt
crontab /tmp/crontab.txt
"""

INIT_SCRIPT = (
    "mkdir ~ec2-user/uploaded; "
    "sudo yum install -y alsa-lib-devel "
    " >~ec2-user/uploaded/install.log 2>~ec2-user/uploaded/install.err.log && "
    "sudo pip install magenta "
    " >~ec2-user/uploaded/install.log 2>~ec2-user/uploaded/install.err.log && "
    "sudo yum --enablerepo epel install -y s3cmd "
    " >~ec2-user/uploaded/install.log 2>~ec2-user/uploaded/install.err.log &&"
    "s3cmd --no-preserve --quiet "
    "--access_key={access_key} --secret_key={secret_key} "
    "sync {s3_url} ~ec2-user/uploaded/"
    " >~ec2-user/uploaded/install.log 2>~ec2-user/uploaded/install.err.log")

# Deep Learning AMI Amazon Linux Version
# https://aws.amazon.com/marketplace/pp/B01M0AXXQB
AMI_IDS = {
    'us-east-1': 'ami-4b44745d',
    'us-east-2': 'ami-305d7c55',
    'us-west-2': 'ami-296e7850',
    'eu-west-1': 'ami-d36386aa',
    'ap-southeast-2': 'ami-52332031',
    'ap-northeast-1': 'ami-b44050d3',
    'ap-northeast-2': 'ami-1523fc7b',
}

DEFAULT_AZ = 'us-east-1c'

INSTANCE_TYPES = {
    'p2.8xlarge': 7.20,
    'p2.xlarge': 0.90,
    'p2.16xlarge': 14.40,
    't2.medium': 0.047,
}

DEFAULT_INSTANCE_TYPE = 'p2.xlarge'
DEFAULT_TAG = 'automagenta'
DEFAULT_S3_DIR = '~/uploaded/'
DEFAULT_COMMAND = 'run.sh'
CUSTOM_TAG_KEY = 'automagenta-project'


class UserAbort(Exception):
    pass


def log(text, color='green'):
    print colored('[automagenta]', color), ':\t', colored(text, color)


def resolve_s3_bucket():
    default_name = "%s-automagenta" % getpass.getuser()

    log("Using S3 bucket '%s'" % default_name)

    s3 = boto3.client('s3')

    try:
        s3.head_bucket(Bucket=default_name)
        return default_name
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            s3.create_bucket(Bucket=default_name)
            return default_name
        elif e.response['Error']['Code'] == '403':
            default_name = default_name + "_1"
            name = raw_input(
                "Create an S3 bucket to store files "
                "(press enter to use: '%s'): " %
                default_name)
            if not name.strip():
                name = default_name
            else:
                name = name.strip()
            s3.create_bucket(Bucket=name)
            return name
        else:
            raise e


def create_or_get_subnet_id():
    ec2 = boto3.client('ec2')
    ec2r = boto3.resource('ec2')
    cidr_block = '10.0.0.0/24'

    existing_subnets = ec2.describe_subnets(Filters=[
        {
            'Name': 'tag-value',
            'Values': [DEFAULT_TAG]
        }
    ])

    for subnet in existing_subnets['Subnets']:
        return subnet['VpcId'], subnet['SubnetId']

    # If we don't find an existing VPC, let's create one and tag it.
    vpc = ec2r.create_vpc(CidrBlock=cidr_block)
    subnet = vpc.create_subnet(
        CidrBlock=cidr_block,
        AvailabilityZone=DEFAULT_AZ)
    ec2.modify_subnet_attribute(
        SubnetId=subnet.id,
        MapPublicIpOnLaunch={'Value': True})
    ec2.create_tags(
        Resources=[subnet.id],
        Tags=[{'Key': 'Name', 'Value': DEFAULT_TAG}])

    list(vpc.security_groups.limit(1))[0].authorize_ingress(
        CidrIp='0.0.0.0/0',
        IpProtocol='tcp',
        FromPort=22,
        ToPort=22)

    gateway = ec2.create_internet_gateway()
    vpc.attach_internet_gateway(
        InternetGatewayId=gateway['InternetGateway']['InternetGatewayId'])
    list(vpc.route_tables.limit(1))[0].create_route(
        DestinationCidrBlock='0.0.0.0/0',
        GatewayId=gateway['InternetGateway']['InternetGatewayId'])
    vpc.create_tags(Tags=[{'Key': 'Name', 'Value': DEFAULT_TAG}])

    return vpc.id, subnet.id


def create_or_get_key_pair():
    default_key_path = os.path.expanduser('~/.automagenta_key.pem')
    default_key_name = DEFAULT_TAG

    if not os.path.exists(default_key_path):
        ec2 = boto3.client('ec2')
        try:
            key_pair = ec2.create_key_pair(KeyName=default_key_name)
        except ClientError as e:
            if e.response['Error']['Code'] == '409':
                ec2.delete_key_pair(KeyName=default_key_name)
                key_pair = ec2.create_key_pair(KeyName=default_key_name)
            else:
                raise e

        with open(default_key_path, 'w') as f:
            f.write(key_pair['KeyMaterial'])
        os.chmod(default_key_path, 0600)

    return default_key_path, default_key_name


def make_init_script(s3_url):
    access_key, secret_key = get_boto_creds()
    return INIT_SCRIPT.format(
        s3_url=s3_url,
        access_key=access_key,
        secret_key=secret_key)


def ssh_args(instance):
    return [
        'ssh', '-t',
        '-o', 'StrictHostKeyChecking=no',
        '-i', '~/.automagenta_key.pem',
        USER_NAME + '@' + instance.public_ip_address
    ]


def start_ssh_session(instance):
    ssh_call = ' '.join(ssh_args(instance))
    subprocess.call(ssh_call, shell=True)


def wait_for_ssh_connectivity(instance, timeout=600):
    start = time.time()
    while True:
        time.sleep(1)
        if time.time() - start > timeout:
            raise ValueError("Failed to connect to SSH within timeout.")
        ssh_call = ' '.join(ssh_args(instance) + ['echo pong;'])
        try:
            result = subprocess.check_output(
                ssh_call,
                stderr=open('/dev/null', 'w'),
                shell=True)
            if 'pong' in result:
                return
        except subprocess.CalledProcessError:
            pass


def run_ssh_command(
    instance, s3_url, command=DEFAULT_S3_DIR + DEFAULT_COMMAND
):
    ssh_call = ' '.join(ssh_args(instance) + [
        ("'"
            + make_init_script(s3_url) + '; '
            + 'bash -ex ' + command + "; "
            + save_to_s3_command(s3_url) + '; \'')
    ])
    # log("Running " + ssh_call)
    subprocess.call(ssh_call, shell=True)


def start_instance(
    tag, s3_url, subnet_id,
    key_name, instance_type=DEFAULT_INSTANCE_TYPE
):
    ec2c = boto3.client('ec2')
    ec2 = boto3.resource('ec2')

    existing_instances = ec2c.describe_instances(Filters=[
        {
            'Name': 'tag-key',
            'Values': [CUSTOM_TAG_KEY],
        },
        {
            'Name': 'tag-value',
            'Values': [tag],
        },
        {
            'Name': 'instance-state-name',
            'Values': ['running'],
        }
    ])

    for reservation in existing_instances['Reservations']:
        for instance in reservation['Instances']:
            log("Using existing instance " + str(instance['InstanceId']))
            return ec2.Instance(instance['InstanceId'])

    log('About to start a %s instance, which costs US$%2.2f '
        'per hour (US$%2.2f per day).' % (
            instance_type,
            INSTANCE_TYPES[instance_type],
            INSTANCE_TYPES[instance_type] * 24), 'red')
    log('This instance will automatically shut down '
        'after 1 hour if not in use.', 'yellow')
    while True:
        confirm = raw_input('Type confirm or cancel, followed by enter: ')
        if confirm == 'cancel':
            raise UserAbort()
        elif confirm == 'confirm':
            break

    instances = ec2.create_instances(
        MinCount=1,
        MaxCount=1,

        ImageId=AMI_IDS[REGION],
        InstanceType=instance_type,
        InstanceInitiatedShutdownBehavior='terminate',

        KeyName=key_name,
        UserData=USER_DATA,
        SubnetId=subnet_id,
    )

    instance = instances[0]

    ec2.create_tags(
        Resources=[instance.id],
        Tags=[
            {'Key': 'Name', 'Value': DEFAULT_TAG},
            {'Key': CUSTOM_TAG_KEY, 'Value': tag}])

    log("Created instance " + str(instance))

    return instance


def get_boto_creds():
    session = boto3.Session()
    credentials = session.get_credentials()

    # Credentials are refreshable, so accessing your access key / secret key
    # separately can lead to a race condition. Use this to get an actual
    # matched set.
    credentials = credentials.get_frozen_credentials()
    access_key = credentials.access_key
    secret_key = credentials.secret_key
    return access_key, secret_key


def sanitized(dir_name):
    return dir_name.replace(' ', '_')


def upload_s3_data(dir_name, bucket):
    access_key, secret_key = get_boto_creds()
    prefix = time.strftime("%Y-%m-%d-%H")
    s3_url = 's3://%s/%s-%s/' % (bucket, prefix, sanitized(dir_name))
    log('Uploading %s to %s...' % (dir_name, s3_url))
    command = ' '.join([
        's3cmd',
        '--quiet',
        '--no-preserve',
        '--access_key=' + access_key,
        '--secret_key=' + secret_key,
        'sync',
        "'" + dir_name + "/'",
        s3_url,
        ' >/dev/null 2>/dev/null',
    ])
    subprocess.call(command, shell=True)
    return s3_url


def download_s3_data(s3_url):
    access_key, secret_key = get_boto_creds()
    command = ' '.join([
        's3cmd',
        '--quiet',
        '--no-preserve',
        '--access_key=' + access_key,
        '--secret_key=' + secret_key,
        'sync',
        s3_url,
        './',
        ' >/dev/null 2>/dev/null',
    ])
    print command
    subprocess.call(command, shell=True)
    return s3_url


def save_to_s3_command(s3_url):
    access_key, secret_key = get_boto_creds()
    url_without_slash = s3_url[:-1]
    s3_url = url_without_slash + '_output/'
    command = ' '.join([
        's3cmd',
        '--quiet',
        '--no-preserve',
        '--access_key=' + access_key,
        '--secret_key=' + secret_key,
        'sync',
        "~/uploaded/",
        s3_url
    ])
    return command

if __name__ == "__main__":
    dir_name = sys.argv[-1]

    if (not os.path.isdir(dir_name)
            or not os.path.isfile(os.path.join(dir_name, DEFAULT_COMMAND))):
        log(
            "Please pass a directory name that "
            "contains a file called `%s`, like this:\n\n"
            "\tautomagenta magenta_experiment_1" % DEFAULT_COMMAND, 'red')
        sys.exit(1)

    bucket = resolve_s3_bucket()
    s3_url = upload_s3_data(dir_name, bucket)

    vpc_id, subnet_id = create_or_get_subnet_id()
    key_path, key_name = create_or_get_key_pair()

    # change MOTD to contain helpful info.
    instance = start_instance(
        sanitized(dir_name),
        s3_url, subnet_id, key_name)

    log("Waiting for instance to start...")
    instance.wait_until_running()
    log("Waiting for public IP address...")

    while not instance.public_ip_address:
        time.sleep(5)
        instance.reload()

    log("Got IP address: " + instance.public_ip_address)

    log('To log onto this instance, run:')
    log("\tssh -t -o StrictHostKeyChecking=no -i "
        "~/.automagenta_key.pem ec2-user@%s" % instance.public_ip_address,
        'yellow')

    log("Waiting for SSH to start...")
    wait_for_ssh_connectivity(instance)
    log("Running run.sh on remote machine...")
    run_ssh_command(instance, s3_url)

    log("Downloading data from S3...")
    download_s3_data(s3_url[:-1] + '_output', dir_name + '_output')
    log("Done!")
