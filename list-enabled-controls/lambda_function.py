import json
import boto3
import os
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Constants - Read environment variables and assign to constants
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


# Function to list enabled controls for a specified OU
def list_controls_for_ou(control_tower_client, ou_id):
    try:
        response = control_tower_client.list_enabled_controls(
            targetIdentifier=f'arn:aws:organizations::{control_tower_account_id}:ou/{organization_id}/{ou_id}'
        )
        return response.get('enabledControls', [])
    except Exception as e:
        # Log and raise an error if there is an issue listing controls
        logger.error(f'Error listing controls for OU: {str(e)}')
        raise


# Main Lambda handler function
def lambda_handler(event, context):
    try:
        # Extract input parameters from the event
        properties = {prop["name"]: prop["value"] for prop in event["requestBody"]["content"]["application/json"]["properties"]}
        region = properties.get('region')
        ou_path = properties.get('ou_path')  # OU path

        # Check for missing parameters and return a 400 error if any are missing
        if not region or not ou_path:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Missing required parameters'})
            }
        
        logger.info(f'Parameters received - Region: {region}, OU Path: {ou_path}')

        # Assume the specified role
        credentials = assume_role(control_tower_account_arn)

        # Create clients for AWS Organizations and Control Tower using the assumed role credentials
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

        # Get the OU ID from the OU path
        ou_id = get_ou_id_from_path(org_client, ou_path.strip())

        # List all controls for the specified OU
        results = list_controls_for_ou(control_tower_client, ou_id)

        # Return success response with the list of enabled controls
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
                            "enabledControls": results
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
