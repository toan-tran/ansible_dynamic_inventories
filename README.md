# Ansible Dynamic OpenStack Inventories

## Introduction

This project provides scripts that dynamically generate Ansible inventory
content from OpenStack virtual machines.

Change that will be modified in near future:
  - Keys are located in current folder

## Usage

- Install requirements
- Copy all the keys to the current folder
- Use the examples in the config folder to create your own configuration files
- (optional) Set the OpenStack credentials to environment variables (e.g. source openrc.sh)
  The environment variables can be put directly to the configuration file
- Run the script to see result or test with Ansible:
    ansible -i openstack_inventory.py all -vvv -m ping
