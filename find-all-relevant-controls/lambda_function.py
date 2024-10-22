import json
import logging
import os
import boto3
from botocore.exceptions import ClientError

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize a Boto3 client for Bedrock
bedrock = boto3.client(service_name='bedrock-runtime')
bedrock_client = boto3.client(service_name='bedrock-agent-runtime')


def invoke_bedrock_model(prompt):
    try:
        # Format the prompt
        formatted_prompt = "\n\nHuman: " + prompt + "\n\nAssistant:"
        body = {
            "modelId": "anthropic.claude-3-sonnet-20240229-v1:0",
            "contentType": "application/json",
            "accept": "*/*",
            "body": {
                "prompt": formatted_prompt,
                "max_tokens_to_sample": 10000,
                "temperature": 0,
                "top_k": 250,
                "top_p": 1,
                "stop_sequences": ["\n\nAssistant:"],
                "anthropic_version": "bedrock-2023-05-31"
            }
        }

        # Invoke the Bedrock model
        response = bedrock.invoke_model(
            body=json.dumps(body['body']),
            modelId=body['modelId'],
            contentType=body['contentType'],
            accept=body['accept']
        )

        # Parse the response from Bedrock
        response_body = json.loads(response['body'].read())
        logger.info(f"Response from Bedrock model: {response_body}")
        return response_body.get('completion', '').strip()
    except ClientError as e:
        logger.error("An error occurred while invoking Bedrock model: %s", e, exc_info=True)
        raise


def retrieve_module_definitions(knowledge_base_id, model_arn, user_description):
    query_text = f"Retrieve ALL relevant identifiers, descriptions for {user_description}. Provide all of them"
    try:
        response = bedrock_client.retrieve_and_generate(
            input={
                'text': query_text
            },
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': knowledge_base_id,
                    'modelArn': model_arn
                }
            }
        )
        
        # Extracting the text from the response
        module_definitions = response['output']['text']
        return module_definitions
    except ClientError as e:
        logger.error("An error occurred:", e)
        return {}


def lambda_handler(event, context):
    try:
        properties = {prop["name"]: prop["value"] for prop in event["requestBody"]["content"]["application/json"]["properties"]}
        user_description = properties.get('user_description')

        if not user_description:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Missing required parameters'})
            }

        logger.info(f'Parameters received - User Description: {user_description}')

        # Knowledge base ID
        kb_id = os.environ['KNOWLEDGE_BASE_ID']

        # Generate Terraform config using Bedrock model
        module_definitions = retrieve_module_definitions(kb_id, "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-v2", user_description)

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
                            "message": f"The control identifiers {module_definitions}"
                        })
                    }
                },
                'sessionAttributes': event.get('sessionAttributes', {}),
                'promptSessionAttributes': event.get('promptSessionAttributes', {})
            }
        }
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        # Ensure that error responses also align with the OpenAPI schema
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                "error": "An error occurred during the process.",
                "details": str(e)
            })
        }
