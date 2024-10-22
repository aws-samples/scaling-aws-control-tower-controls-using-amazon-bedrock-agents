import json
import boto3
import os
import logging
from botocore.exceptions import ClientError

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Fetch environment variables
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
        # Log and raise an error if role assumption fails
        logger.error(f'Error assuming role: {str(e)}')
        raise


# Function to get the Organizational Unit (OU) ID from its path
def get_ou_id_from_path(org_client, ou_path):
    parent_id = control_tower_root_id  # Use the root ID from environment variables
    ou_parts = ou_path.split('/')
    
    try:
        # Traverse the OU hierarchy using the given path
        for part in ou_parts:
            response = org_client.list_organizational_units_for_parent(ParentId=parent_id)
            found = False
            for ou in response['OrganizationalUnits']:
                if ou['Name'] == part:
                    parent_id = ou['Id']
                    found = True
                    break
            if not found:
                # Raise an error if the OU path is not found
                raise ValueError(f"OU path '{ou_path}' not found")
    except Exception as e:
        # Log and raise an error if there is an issue getting the OU ID
        logger.error(f'Error getting OU ID from path: {str(e)}')
        raise
    return parent_id


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
        logger.error(f"Error checking control status: {str(e)}")
        raise


def enable_control(control_tower_client, control_arn, ou_arn):
    try:
        logger.info(f'Enabling control {control_arn} for OU {ou_arn}')
        response = control_tower_client.enable_control(
            controlIdentifier=control_arn,
            targetIdentifier=ou_arn
        )
        return response
    except ClientError as e:
        logger.error(f"Error enabling control: {str(e)}")
        raise


def disable_control(control_tower_client, control_arn, ou_arn):
    try:
        logger.info(f'Disabling control {control_arn} for OU {ou_arn}')
        response = control_tower_client.disable_control(
            controlIdentifier=control_arn,
            targetIdentifier=ou_arn
        )
        return response
    except ClientError as e:
        logger.error(f"Error disabling control: {str(e)}")
        raise


def lambda_handler(event, context):
    # Print the entire event
    logger.info("Received event: " + json.dumps(event))

    # Extract input parameters
    properties = {prop["name"]: prop["value"] for prop in event["requestBody"]["content"]["application/json"]["properties"]}
    region = properties.get('region')
    ou_path = properties.get('ou_path')  # Single OU
    operation = properties.get('operation')  # 'enable' or 'disable'
    control_identifier = properties.get('controlidentifer')
    
    if not region or not ou_path or not operation or not control_identifier:
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Missing required parameters'})
        }

    logger.info(f'Parameters received - Region: {region}, OU Path: {ou_path}, Operation: {operation}, Control Identifier: {control_identifier}')

    try:
        # Assume the specified role
        credentials = assume_role(control_tower_account_arn)
        
        org_client = boto3.client(
            'organizations',
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
        
        control_tower_client = boto3.client(
            'controltower',
            region_name=region,
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )

        control_arn = f'arn:aws:controltower:{region}::control/{control_identifier}'

        # Get OU ID from path
        ou_id = get_ou_id_from_path(org_client, ou_path.strip())
        ou_arn = f'arn:aws:organizations::{control_tower_account_id}:ou/{organization_id}/{ou_id}'
        
        # Check current control status
        is_enabled = check_control_status(control_tower_client, control_arn, ou_arn)
        
        if operation == 'enable':
            if is_enabled:
                message = f"Control {control_identifier} is already enabled for OU {ou_id}."
            else:
                response = enable_control(control_tower_client, control_arn, ou_arn)
                message = f"Control {control_identifier} has been enabled for OU {ou_id}."
        elif operation == 'disable':
            if not is_enabled:
                message = f"Control {control_identifier} is already disabled for OU {ou_id}."
            else:
                response = disable_control(control_tower_client, control_arn, ou_arn)
                message = f"Control {control_identifier} has been disabled for OU {ou_id}."
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Invalid operation. Use "enable" or "disable".'})
            }

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
                            "message": f"The requested operation has been completed: {message}"
                        })
                    }
                },
                'sessionAttributes': event.get('sessionAttributes', {}),
                'promptSessionAttributes': event.get('promptSessionAttributes', {})
            }
        }
    except ValueError as ve:
        # Handle value errors specifically and log them
        logger.error(f'Value error: {str(ve)}')
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event['actionGroup'],
                'apiPath': event['apiPath'],
                'httpMethod': event['httpMethod'],
                'httpStatusCode': 200,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps({'message': 'Value error', 'error': str(ve)})
                    }
                },
                'sessionAttributes': event.get('sessionAttributes', {}),
                'promptSessionAttributes': event.get('promptSessionAttributes', {})
            }
        }
    except Exception as e:
        # Handle unexpected errors and log them
        logger.error(f'Unexpected error: {str(e)}')
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event['actionGroup'],
                'apiPath': event['apiPath'],
                'httpMethod': event['httpMethod'],
                'httpStatusCode': 200,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps({'message': 'Unexpected error', 'error': str(e)})
                    }
                },
                'sessionAttributes': event.get('sessionAttributes', {}),
                'promptSessionAttributes': event.get('promptSessionAttributes', {})
            }
        }
