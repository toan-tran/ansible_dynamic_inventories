# Ansible Dynamic OpenStack Inventories

## Introduction

This project provides scripts that dynamically generate Ansible inventory
content from OpenStack virtual machines or create VMs based on existing
inventory.

Scripts:

  - openstack_inventory.py: Generate inventory from OpenStack platform
  - openstack_upload_metadata.py: Populate metadata to VMs matching an existing inventory


## Installation

- Install depedencies
    ```sh
    pip install -r requirements.txt
    ```
- Use the examples in the config folder to create your own configuration files
  
  IMPORTANT: If 'ansible_private_key_file' is specified,
             Make sur that all private keys are stored in the 'key_folder'.

  NOTE: If OpenStack credentials are not specified in the config file, user must 
        specify them in environment variables (e.g. source openrc.sh)

## Usage

### 1. openstack_inventory.py:

- Test the output of the script:
    ```sh
    python openstack_inventory.py
    ```
- Test the script to see result or test with Ansible:
    ```sh
    ansible -i openstack_inventory.py all -vvv -m ping
    ```

### 2. openstack_upload_metadata.py:

- Make sur that the existing VMs on OpenStack platform match their name in the inventory

- Populate VMs' metadata:
    ```sh
    ./openstack_upload_metadata.py <inventory_file>
    ```

- More options on openstack_upload_metadata.py:
    ```sh
    ./openstack_upload_metadata.py [-o template] [--no-update] <inventory_file>
        -o template, --out-template template
                              Save the template of the inventory in a file
        -n, --no-update       If set, do not update metadata of the VMs
    ```
    

