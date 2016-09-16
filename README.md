# Ansible Dynamic OpenStack Inventories

## Introduction

This project provides scripts that dynamically generate Ansible inventory
content from OpenStack virtual machines.

Change that will be modified in near future:

  - Script uses instances UUID as their identity.
  - Keys are located in current folder

## Usage

- Install requirements
- Copy all the keys to the current folder
- Set the OpenStack credentials to environment variables (e.g. source openrc.sh)
- Run the script to see result or test with Ansible:
    ansible -i openstack_inventory.py all -vvv -m ping
