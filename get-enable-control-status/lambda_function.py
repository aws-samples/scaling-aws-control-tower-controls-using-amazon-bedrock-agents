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


def get_enabled_control(control_tower_client, enabled_control_arn):
    try:
        response = control_tower_client.get_enabled_control(
            enabledControlIdentifier=enabled_control_arn
        )
        return response
    except ClientError as e:
        logger.error(f"Error getting enabled control: {str(e)}")
        raise


def lambda_handler(event, context):
    logger.info("Received event: " + json.dumps(event))

    # Extract input parameters
    properties = {prop["name"]: prop["value"] for prop in event["requestBody"]["content"]["application/json"]["properties"]}
    region = properties.get('region')
    enabled_control_arn = properties.get('enabled_control_arn')

    if not enabled_control_arn or not region:
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Missing required parameter'})
        }

    try:
        credentials = assume_role(control_tower_account_arn)

        control_tower_client = boto3.client('controltower',
            region_name=region,
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
        
        response = get_enabled_control(control_tower_client, enabled_control_arn)

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
                            "enabledControls": response
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
