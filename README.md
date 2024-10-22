# Scaling AWS Control Tower controls using Amazon Bedrock Agents

---

#### Overview
This README documents five AWS Lambda functions designed for working with AWS Control Tower controls along with Amazon Bedrock Knowledge Base (KB) and Amazon Bedrock Agent instructions. This solution follows AWS security reference architecture(https://docs.aws.amazon.com/prescriptive-guidance/latest/security-reference-architecture/architecture.html), and can be utilized to work with AWS Control Tower controls via Control APIs.

#### Solution Overview
1. The user interacts with Amazon Bedrock Agent via a chat console, specifying actions such as enable, disable, list or get enabled control status/information.
2. The agent processes the user's request, identifies the required parameters, and queries the user for additional information if necessary.
3. The agent uses the Knowledge Base to retrieve detailed information about each control, along with information about ARNs and control identifiers.
4. The agent triggers the appropriate action group based on the user's request. 
        1. find all relevant controls : find all relevant controls (identifiers) for a use-case
        2. list enabled controls: Retrieves a list of currently enabled controls for a region and OU.
        3. enable/disable control: handles requests to enable or disable a control using AWS Control Tower API for a particular region and OU. 
        4. bulk enable/disable controls: handles requests to enable or disable a set of controls using AWS Control Tower APIs for multiple OUs.
        5. get enable control status: get enabled control status/information for a specific conrtol. 
5. The Lambda functions associated to the action group perform the necessary actions by calling AWS Control Tower APIs with the needed parameters. AWS Control Tower executes the requested actions and manages the controls as specified by the bedrock agent

#### Find All Relevant Controls Lambda

- **Description**: Find the relevant control identifiers with user provided description
- **Environment Variables**:
  - `KNOWLEDGE_BASE_ID`: ID of created Knowledge base
- **Logical Flow**:
    1. Receives an event with the user's description of the desired control.
    2. Searches the knowledge base and finds all relevant control identifiers.
    3. Returns the information back to Bedrock agent.

#### List Enabled Controls
- **Description**: List all enabled controls for a region and an OU
- **Environment Variables**:
  - `control_tower_account_arn`: IAM role to access control tower account
  - `control_tower_account_id`: Control tower account ID
  - `control_tower_root_id`: Control tower root ID
  - `organization_id`: Organization ID
- **Logical Flow**:
    1. Receives an event with a region and OU path.
    2. Fetches the OU ID from provided OU path.
    3. Get the list of enabled controls for that provided region and OU
    3. Returns the information back to Bedrock agent.

#### Enable/Disable Control
- **Description**: Enable or disable a control using AWS Control Tower API for a particular region and OU. 
- **Environment Variables**:
  - `control_tower_account_arn`: IAM role to access control tower account
  - `control_tower_account_id`: Control tower account ID
  - `control_tower_root_id`: Control tower root ID
  - `organization_id`: Organization ID
- **Logical Flow**:
    1. Receives an event with region, OU path, operation(enable/disable) and control identifier.
    2. Fetches the OU ID from provided OU path.
    3. Checks the current state of the control for that particular region, OU and updates it as per the operation provided.
    4. Returns the success/failure message back to Bedrock agent.

#### Bulk Enable/Disable Control
- **Description**: Bulk Enable or disable a set of controls using AWS Control Tower APIs for multiple OUs. 
- **Environment Variables**:
  - `control_tower_account_arn`: IAM role to access control tower account
  - `control_tower_account_id`: Control tower account ID
  - `control_tower_root_id`: Control tower root ID
  - `organization_id`: Organization ID
- **Logical Flow**:
    1. Receives an event with multiple OU paths, operation(enable/disable), control tower home region name and control identifiers.
    2. Fetches the OU IDs from provided OU paths.
    3. Checks the current state of each control for that particular region, OU and updates it as per the operation provided.
    4. Returns the success/failure message back to Bedrock agent.

#### Get Enable Control Status
- **Description**: Get enabled control status/information for a specific conrtol. 
- **Environment Variables**:
  - `control_tower_account_arn`: IAM role to access control tower account
- **Logical Flow**:
    1. Receives an event with region and enabled control arn.
    2. Fetches the enabled control status/information
    3. Returns the success/failure message back to Bedrock agent.

#### Knowledge Base (KB)
- **Description**: A structured repository containing Control Identifiers and their description.
- **Structure**: JSON format categorizing control identifiers and descriptions.
- **Configure Knowledge Base**: Configuring a Knowledge Base (KB) enables your Bedrock agents to access a repository of information for Control Tower Control APIs. Follow these steps to set up your KB:
  1. Access the Amazon Bedrock Console: Log in and go directly to the 'Knowledge Base' section. This is your starting point for creating a new KB.
  2. Name Your Knowledge Base: Choose a clear and descriptive name that reflects the purpose of your KB, such as "Control Tower APIs"
  3. Select an IAM Role: Assign a pre-configured IAM role with the necessary permissions. 
  4. Define the Data Source: Upload a JSON file to an S3 bucket with encryption enabled for security. This file should contain a structured list of AWS services and Terraform modules. For the JSON structure, use the example provided in this repository
  5. Choose the Default Embeddings Model: For most use cases, the Amazon Bedrock Titan G1 Embeddings - Text model will suffice. It's pre-configured and ready to use, simplifying the process.
  6. Opt for the Managed Vector Store: Allow Amazon Bedrock to create and manage the vector store for you in Amazon OpenSearch Service.
  7. Review and Finalize: Double-check all entered information for accuracy. Pay special attention to the S3 bucket URI and IAM role details.

#### Updating and Maintenance
- **Lambda Functions**:
  - Regularly update dependencies and environment variables.
  - Monitor Lambda logs for troubleshooting.
- **Knowledge Base**:
  - Regularly update with new AWS services and modules.
  - Validate JSON structure after updates.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
