import json
import boto3
import os
import logging
from botocore.exceptions import ClientError

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Constants from environment variables
control_tower_account_arn = os.environ['control_tower_account_arn']
control_tower_account_id = os.environ['control_tower_account_id']
organization_id = os.environ['organization_id']
control_tower_root_id = os.environ['control_tower_root_id']


# Function to assume a role and get temporary credentials
def assume_role(role_arn):
    sts_client = boto3.client('sts')
    try:
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName='ControlTowerSession'
        )
        credentials = response['Credentials']
        return credentials
    except Exception as e:
        logger.error(f'Error assuming role: {str(e)}')
        raise


# Function to get the Organizational Unit (OU) ID from its path
def get_ou_id_from_path(org_client, ou_path):
    parent_id = control_tower_root_id  # Use the root ID from environment variables
    ou_parts = ou_path.split('/')
    
    try:
        for part in ou_parts:
            response = org_client.list_organizational_units_for_parent(ParentId=parent_id)
            found = False
            for ou in response['OrganizationalUnits']:
                if ou['Name'] == part:
                    parent_id = ou['Id']
                    found = True
                    break
            if not found:
                raise ValueError(f"OU path '{ou_path}' not found")
    except Exception as e:
        logger.error(f'Error getting OU ID from path: {str(e)}')
        raise 
    return parent_id


# Function to check if a control is enabled
def check_control_status(control_tower_client, control_arn, ou_arn):
    try:
        response = control_tower_client.list_enabled_controls(
            targetIdentifier=ou_arn
        )
        logger.info(f'Response from list_enabled_controls: {response}')
        enabled_controls = response.get('enabledControls', [])
        for control in enabled_controls:
            if control['controlIdentifier'] == control_arn:
                return True
        return False
    except ClientError as e:
        logger.error(f'Error checking control status: {str(e)}')
        raise


# Function to enable a control
def enable_control(control_tower_client, control_arn, ou_arn):
    try:
        logger.info(f'Enabling control {control_arn} for OU {ou_arn}')
        response = control_tower_client.enable_control(
            controlIdentifier=control_arn,
            targetIdentifier=ou_arn
        )
        logger.info(f'Response from enable_control: {response}')
        return response
    except ClientError as e:
        logger.error(f'Error enabling control: {str(e)}')
        raise


# Function to disable a control
def disable_control(control_tower_client, control_arn, ou_arn):
    try:
        logger.info(f'Disabling control {control_arn} for OU {ou_arn}')
        response = control_tower_client.disable_control(
            controlIdentifier=control_arn,
            targetIdentifier=ou_arn
        )
        logger.info(f'Response from disable_control: {response}')
        return response
    except ClientError as e:
        logger.error(f'Error disabling control: {str(e)}')
        raise


def lambda_handler(event, context):
    logger.info("Received event: " + json.dumps(event))

    properties = {prop["name"]: prop["value"] for prop in event["requestBody"]["content"]["application/json"]["properties"]}
    region = properties.get('region', '')  # Single region as input
    ou_paths = properties.get('ou_path', '').split(',')  # Split the OUs by comma
    operations = properties.get('operation', '').split(',')  # Split the operations by comma
    control_identifiers = properties.get('controlidentifer', '').split(',')  # Split the control identifiers by comma
    
    if not region or not ou_paths or not operations or not control_identifiers:
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Missing required parameters'})
        }

    logger.info(f'Parameters received - Region: {region}, OU Paths: {ou_paths}, Operations: {operations}, Control Identifiers: {control_identifiers}')

    try:
        credentials = assume_role(control_tower_account_arn)
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Error assuming role: {str(e)}'})
        }
    
    org_client = boto3.client(
        'organizations',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )
    
    results = []

    try:
        control_tower_client = boto3.client(
            'controltower',
            region_name=region,
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
        
        for control_identifier in control_identifiers:
            control_arn = f'arn:aws:controltower:{region}::control/{control_identifier}'
            
            for ou_path in ou_paths:
                try:
                    ou_id = get_ou_id_from_path(org_client, ou_path.strip())
                    ou_arn = f'arn:aws:organizations::{control_tower_account_id}:ou/{organization_id}/{ou_id}'
                    
                    for operation in operations:
                        try:
                            is_enabled = check_control_status(control_tower_client, control_arn, ou_arn)
                            if operation == 'enable':
                                if is_enabled:
                                    message = f"Control {control_identifier} is already enabled for OU {ou_id}."
                                else:
                                    enable_control(control_tower_client, control_arn, ou_arn)
                                    message = f"Control {control_identifier} has been enabled for OU {ou_id}."
                            elif operation == 'disable':
                                if not is_enabled:
                                    message = f"Control {control_identifier} is already disabled for OU {ou_id}."
                                else:
                                    disable_control(control_tower_client, control_arn, ou_arn)
                                    message = f"Control {control_identifier} has been disabled for OU {ou_id}."
                            else:
                                raise ValueError('Invalid operation. Use "enable" or "disable".')
                            results.append({"region": region, "control_identifier": control_identifier, "ou_path": ou_path, "ou_id": ou_id, "operation": operation, "message": message})
                        except Exception as e:
                            logger.error(f'Error for operation {operation} on control {control_identifier} for OU path {ou_path}: {str(e)}')
                            results.append({"region": region, "control_identifier": control_identifier, "ou_path": ou_path, "operation": operation, "error": str(e)})
                except Exception as e:
                    logger.error(f'Error for OU path {ou_path}: {str(e)}')
                    results.append({"region": region, "control_identifier": control_identifier, "ou_path": ou_path, "error": str(e)})

        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event['actionGroup'],
                'apiPath': event['apiPath'],
                'httpMethod': event['httpMethod'],
                'httpStatusCode': 200,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps({
                            "results": results
                        })
                    }
                },
                'sessionAttributes': event.get('sessionAttributes', {}),
                'promptSessionAttributes': event.get('promptSessionAttributes', {})
            }
        }
    except Exception as e:
        logger.error(f'Unexpected error: {str(e)}')
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
