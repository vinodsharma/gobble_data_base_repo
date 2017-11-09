from os.path import join, dirname
import os.path
from dotenv import load_dotenv
import os
import boto3
from botocore.exceptions import ClientError as BotoClientError
from time import sleep
import subprocess
import json
import src.app_utils.settings as settings
import textwrap
import argparse


batch_client = boto3.client('batch')
ec2_client = boto3.client('ec2')
lambda_client = boto3.client('lambda')
events_client = boto3.client('events')


class Deploy_Exception(Exception):
    pass


def get_deploy_settings():
    dotenv_path = join(dirname('.'), '.env')
    load_dotenv(dotenv_path)
    deploy_settings = {
            'DOCKER_IMAGE': os.getenv('DOCKER_IMAGE'),
    }
    deploy_settings.update(settings.get_settings_dict())
    return deploy_settings


def is_compute_env_exists(compute_env_name):
    response = batch_client.describe_compute_environments(
        computeEnvironments=[
            compute_env_name,
        ],
    )
    if len(response['computeEnvironments']) == 1:
        return True
    else:
        return False


def get_default_vpc_id():
    vpcs_info = ec2_client.describe_vpcs(
        Filters=[
            {
                'Name': 'isDefault',
                'Values': [
                    'true',
                ]
            },
        ],
    )
    if len(vpcs_info['Vpcs']) < 1:
        raise Deploy_Exception("No Default VPC Exists")
    vpc_id = vpcs_info['Vpcs'][0]['VpcId']
    return vpc_id


def get_security_group_ids(vpc_id):
    security_groups_info = ec2_client.describe_security_groups(
        Filters=[
            {
                'Name': 'vpc-id',
                'Values': [
                    vpc_id,
                ]
            },
        ],
        GroupNames=[
            'default',
        ],
    )
    if len(security_groups_info['SecurityGroups']) < 1:
        raise Deploy_Exception(
            "No SecurityGroup exits for the vpc-id %s" % vpc_id)

    security_group_ids = []
    for security_group in security_groups_info['SecurityGroups']:
        security_group_ids.append(security_group['GroupId'])
    return security_group_ids


def get_subnet_ids(vpc_id):
    subnets_info = ec2_client.describe_subnets(
        Filters=[
            {
                'Name': 'vpc-id',
                'Values': [
                    vpc_id,
                ]
            },
            {
                'Name': 'default-for-az',
                'Values': [
                    'true',
                ]
            },
        ],
    )
    if len(subnets_info['Subnets']) < 1:
        raise Deploy_Exception("No Subnet exits for the vpc-id %s" % vpc_id)

    subnet_ids = []
    for subnet in subnets_info['Subnets']:
        subnet_ids.append(subnet['SubnetId'])
    return subnet_ids


def create_compute_env(compute_env_name, aws_account_id):
    vpc_id = get_default_vpc_id()
    instance_types = ['optimal', 'm4']
    batch_client.create_compute_environment(
        type='MANAGED',
        computeEnvironmentName=compute_env_name,
        computeResources={
            'type': 'EC2',
            'instanceRole': 'arn:aws:iam::' + aws_account_id +
            ':instance-profile/ecsInstanceRole',
            'instanceTypes': instance_types,
            'maxvCpus': 256,
            'minvCpus': 0,
            'securityGroupIds': get_security_group_ids(vpc_id),
            'subnets': get_subnet_ids(vpc_id),
            'tags': {
                'Name': 'Batch Instance - '+compute_env_name,
            },
        },
        serviceRole='arn:aws:iam::' + aws_account_id +
        ':role/service-role/AWSBatchServiceRole',
        state='ENABLED',
    )


def wait_until_compute_env_is_ready(compute_env_name):
    for i in range(30):
        sleep(10)
        response = batch_client.describe_compute_environments(
            computeEnvironments=[compute_env_name])
        comp_env = response['computeEnvironments'][0]
        if comp_env['status'] == 'VALID':
            return
    raise Deploy_Exception(
        "TimeOut: Compute Environemnt %s is not ready" % compute_env_name)


def is_job_queue_exists(job_queue_name):
    response = batch_client.describe_job_queues(
        jobQueues=[
            job_queue_name,
        ],
    )

    if len(response['jobQueues']) == 1:
        return True
    else:
        return False


def create_job_queue(job_queue_name, compute_env_name):
    batch_client.create_job_queue(
        computeEnvironmentOrder=[
            {
                'computeEnvironment': compute_env_name,
                'order': 1,
            },
        ],
        jobQueueName=job_queue_name,
        priority=1,
        state='ENABLED',
    )


def register_job_definition(job_definition_name, docker_image,
                            shell_script_to_run_app):
    response = batch_client.register_job_definition(
        type='container',
        containerProperties={
            'command': [
                'sh',
                shell_script_to_run_app,
            ],
            'image': docker_image,
            'memory': 1024*6,
            'vcpus': 2,
        },
        jobDefinitionName=job_definition_name,
    )
    return response


def get_function(aws_lambda_function_name):
    response = lambda_client.get_function(
        FunctionName=aws_lambda_function_name
    )
    return response


def is_function_exists(aws_lambda_function_name):
    try:
        get_function(aws_lambda_function_name)
        return True
    except BotoClientError as bce:
        if bce.response['Error']['Code'] == 'ResourceNotFoundException':
            return False
        raise


def create_zip_file_for_code(zip_file_name, code_file_name):
    subprocess.check_output(["zip", zip_file_name, code_file_name])


def create_function(fn_role, aws_lambda_function_name):
    zip_file_name = aws_lambda_function_name + ".zip"
    code_file_name = aws_lambda_function_name + ".py"
    create_zip_file_for_code(zip_file_name, code_file_name)
    lambda_client.create_function(
        FunctionName=aws_lambda_function_name,
        Runtime='python3.6',
        Role=fn_role,
        Handler="{0}.lambda_handler".format(aws_lambda_function_name),
        Code={'ZipFile': open("{0}.zip".format(
            aws_lambda_function_name), 'rb').read(), },
    )


def update_function(fn_role, aws_lambda_function_name):
    zip_file_name = aws_lambda_function_name + ".zip"
    code_file_name = aws_lambda_function_name + ".py"
    create_zip_file_for_code(zip_file_name, code_file_name)
    lambda_client.update_function_code(
        FunctionName=aws_lambda_function_name,
        Publish=True,
        ZipFile=open("{0}.zip".format(aws_lambda_function_name), 'rb').read()
    )
    lambda_client.update_function_configuration(
        FunctionName=aws_lambda_function_name,
        Role=fn_role,
    )


def get_function_arn(aws_lambda_function_name):
    response = lambda_client.get_function_configuration(
        FunctionName=aws_lambda_function_name
    )
    return response['FunctionArn']


def put_rule(rule_name, schedule_expression):
    events_client.put_rule(
        Name=rule_name,
        ScheduleExpression=schedule_expression,
        State='ENABLED',
    )


def add_permissions(aws_lambda_function_name, rule_name):
    try:
        lambda_client.add_permission(
            FunctionName=aws_lambda_function_name,
            StatementId="{0}-Event".format(rule_name),
            Action='lambda:InvokeFunction',
            Principal='events.amazonaws.com',
            SourceArn=get_rule_arn(rule_name),
        )
    except BotoClientError as bce:
        if not bce.response['Error']['Code'] == 'ResourceConflictException':
            raise


def put_targets(fn_arn, rule_name, input_string):
    events_client.put_targets(
        Rule=rule_name,
        Targets=[
            {
                'Id': "1",
                'Arn': fn_arn,
                'Input': input_string,
            },
        ]
    )


def get_rule_arn(rule_name):
    response = events_client.describe_rule(
        Name=rule_name
    )
    return response['Arn']


def create_aws_lambda_function_code(function_name, repo_name):
    aws_lambda_function_file = function_name+".py"
    with open(aws_lambda_function_file, 'w') as function_file:
        function_code = \
            """
            import boto3
            import logging
            import sys

            logger = logging.getLogger('{git_repo_name}_aws_lambda')
            logger.setLevel(logging.DEBUG)

            ch = logging.StreamHandler(sys.stdout)
            ch.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)


            def submit_job(batch_client, job_definition_name, job_name,
                            job_queue_name, env_variables):
                response = batch_client.submit_job(
                    jobDefinition=job_definition_name,
                    jobName=job_name,
                    jobQueue=job_queue_name,
                    containerOverrides={{
                        'environment': env_variables,
                    }},
                )
                logger.info('Submit job response %s', response)


            def create_batch_job_env_variables(event):
                env_variables = []
                for key, value in event.items():
                    env_variables.append({{'name': key, 'value': str(value)}})
                return env_variables


            def lambda_handler(event, context):
                logger.info('submit_job Started')
                job_queue_name = '{git_repo_name}_job_queue'
                job_definition_name = '{git_repo_name}_job_definition'
                job_name = '{git_repo_name}_job'
                env_variables = create_batch_job_env_variables(event)
                batch_client = boto3.client('batch')
                submit_job(batch_client, job_definition_name, job_name,
                            job_queue_name, env_variables)
                logger.info('submit_job Completed')
            """
        function_file.write(textwrap.dedent(
            function_code.format(git_repo_name=repo_name)
        ))
        return aws_lambda_function_file


def create_update_aws_batch_resources(
        aws_account_id, compute_env_name, job_queue_name, job_definition_name,
        docker_image, shell_script_to_run_app):
    if not is_compute_env_exists(compute_env_name):
        create_compute_env(compute_env_name, aws_account_id)
        print("Compute environment %s is created" % compute_env_name)
        print("Waiting for compute environment to be ready")
        wait_until_compute_env_is_ready(compute_env_name)

    if not is_job_queue_exists(job_queue_name):
        create_job_queue(job_queue_name, compute_env_name)
        print("Job queue %s is created" % job_queue_name)

    register_job_definition(job_definition_name, docker_image,
                            shell_script_to_run_app)
    print("Job definition is registered")


def create_update_aws_lambda_function(
        aws_account_id, aws_lambda_function_name, repo_name):
    create_aws_lambda_function_code(aws_lambda_function_name, repo_name)
    fn_role = 'arn:aws:iam::' + aws_account_id + \
        ':role/service-role/LambdaBatchSubmitJobRole'
    if is_function_exists(aws_lambda_function_name):
        update_function(fn_role, aws_lambda_function_name)
        print("Lambda function %s updated" % aws_lambda_function_name)
    else:
        create_function(fn_role, aws_lambda_function_name)
        print("Lambda function %s created" % aws_lambda_function_name)


def create_update_aws_cloudwatch_trigger(
        aws_lambda_function_name, deploy_settings, schedule_expression):
    fn_arn = get_function_arn(aws_lambda_function_name)
    rule_name = "{0}-trigger".format(aws_lambda_function_name)
    put_rule(rule_name, schedule_expression)
    add_permissions(aws_lambda_function_name, rule_name)
    put_targets(fn_arn, rule_name, json.dumps(deploy_settings))
    print("Cloudwatch trigger %s added/updated" % rule_name)


def parse_command_line_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-r', '--repo_name', required=True,
        help='name of the repo: ex: dataengineering')
    parser.add_argument(
        '-s', '--shell_script_to_run_app', required=True,
        help='name of the python file that runs the application.\n\
        Example: dataengineering.py \n\
        Note: deploy script and application python file must be in the same \
        directory')
    command_line_args = parser.parse_args()
    if not os.path.isfile(command_line_args.shell_script_to_run_app):
        raise Deploy_Exception(
            "app python file %s doesn't exists"
            % command_line_args.shell_script_to_run_app)
    return command_line_args


def main():
    print("Deployment Started")

    command_line_args = parse_command_line_args()
    compute_env_name = command_line_args.repo_name + '_comp_env'
    job_queue_name = command_line_args.repo_name + '_job_queue'
    job_definition_name = command_line_args.repo_name + '_job_definition'
    aws_lambda_function_name = command_line_args.repo_name +\
        "_aws_lambda_function"
    deploy_settings = get_deploy_settings()
    docker_image = deploy_settings["DOCKER_IMAGE"]
    aws_account_id = boto3.client('sts').get_caller_identity().get('Account')
    schedule_expression = "cron(0 8 ? * * *)"

    create_update_aws_batch_resources(
        aws_account_id, compute_env_name, job_queue_name, job_definition_name,
        docker_image, command_line_args.shell_script_to_run_app)

    create_update_aws_lambda_function(
        aws_account_id, aws_lambda_function_name, command_line_args.repo_name)

    create_update_aws_cloudwatch_trigger(
        aws_lambda_function_name, deploy_settings, schedule_expression)

    print("Deployed Successfully")


if __name__ == "__main__":
    main()
