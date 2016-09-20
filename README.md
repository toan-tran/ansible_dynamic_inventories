# Ansible Dynamic OpenStack Inventories

## Introduction

This project provides scripts that dynamically generate Ansible inventory
content from OpenStack virtual machines.

## Usage

- Install requirements
    ```sh
    pip install -r requirements.txt
    ```
- Use the examples in the config folder to create your own configuration files
  
  IMPORTANT: If 'ansible_private_key_file' is specified,
             Make sur that all private keys are stored in the 'key_folder'.

  NOTE: If OpenStack credentials are not specified in the config file, user must 
        specify them in environment variables (e.g. source openrc.sh)

- Test the output of the script:
    ```sh
    python openstack_inventory.py
    ```
- Test the script to see result or test with Ansible:
    ```sh
    ansible -i openstack_inventory.py all -vvv -m ping
    ```
