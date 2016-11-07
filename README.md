# Ansible Dynamic OpenStack Inventories


## Introduction

This project provides scripts that dynamically generate Ansible inventory
content from OpenStack virtual machines or create VMs based on existing
inventory.

Scripts:

  - openstack_inventory.py: Generates inventory from OpenStack platform
  - openstack_upload_metadata.py: Populates metadata to VMs matching an
                                  existing inventory
  - openstack_push.py: Generates VMs on OpenStack platform based on an
                       existing inventory


## Installation

- Install depedencies

    ````
    pip install -r requirements.txt
    ````

- Use the examples in the config folder to create your own configuration files
  
  *IMPORTANT*: If 'ansible_private_key_file' is specified, make sur that all
               private keys are stored in the folder indicated by 'key_folder'.

  *NOTE*: If OpenStack credentials are not specified in the config file, user
          must specify them in environment variables (e.g. source openrc.sh).
          Environment variables always take precedence over config variables.

- The scripts will search in following locations for the configuration file
by the order:

    - Current folder
    - .ansible/
    - ~/.ansible/
    - /etc/ansible/


## Usage


### 1. openstack_inventory.py:

- Test the output of the script:

    ````
    python openstack_inventory.py
    ````

- Test the script to see result or test with Ansible:

    ````
    ansible -i openstack_inventory.py all -vvv -m ping
    ````


### 2. openstack_upload_metadata.py:

- Updates metadata for existing VMs based on an Ansible inventory (INI) file.
Will also set correspondent metadata and create a template file.

- Usage:

    ````
    ./openstack_upload_metadata.py [-o template] [--no-update] <inventory_file>
        inventory             Inventory file (INI format)
        -o template, --out-template template
                              Save the template of the inventory in a file
        -n, --no-update       If set, do not update metadata of the VMs
    ````

- *Note* Make sur that the existing VMs on OpenStack platform match their name
in the inventory


### 3. openstack_push.py:

- Creates VMs on OpenStack based on an Ansible inventory (INI) file. Will also
set correspondent metadata and create a template file. If a new host is added
into the inventory, a new VM is created with correspondent metadata. If a host
is removed from the inventory, the correspondent VM will also be removed. All
changes in groups/variables of existing hosts will also be updated into the
metadata.

- Usage:

    ````
    ./openstack_push.py [-h] [-o template] [-n] [-t] inventory
        inventory             Inventory file (INI format)
        -h, --help            show this help message and exit
        -o template, --out-template template
                              Save the template of the inventory in a file
        -n, --no-template     If set, will not create a template file, but save
                              inherited variables in the hosts' metadata
        -t, --trial           If set, will not update the platform, butshow the list
                              of actions
    ````

- The script searches for following variables for each host in the inventory:

    - **openstack_flavor_id**: (required) VM Flavor
    - **openstack_image_id**: (required) VM Image
    - **openstack_network_id**: (required) VM's network. Must be in the same IP
                                range as VM's IP
    - **openstack_security_groups**: (optional) VM's security groups, separated
                                     by comma (,)
    - **openstack_keypair_id**: (optional) VM SSH key name.

  These variables can be put in group vars or host vars, with the laters
overriding the formers.

- *Note*: If "ansible_private_key_file" and "openstack_keypair_id" are defined
for a host, the script will use "ansible_private_key_file".
