#!/usr//bin/env python
# Copyright Khanh-Toan TRAN <khtoantran@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# OpenStack dynamic inventory for Ansible
# This script provides inventory content for Ansible from OpenStack's VMs
#

import json
from novaclient import client
import os


def get_client():
    version = os.environ.get('OS_VERSION', 2)
    auth_url = os.environ.get('OS_AUTH_URL')
    if not auth_url:
        print "ERROR: OS_AUTH_URL is not set"
        return None
    username = os.environ.get('OS_USERNAME')
    if not username:
        print "ERROR: OS_USERNAME is not set"
        return None
    password = os.environ.get('OS_PASSWORD')
    if not password:
        print "ERROR: OS_PASSWORD is not set"
        return None
    tenant_id = os.environ.get('OS_TENANT_ID')
    if not tenant_id:
        print "ERROR: OS_TENANT_ID is not set"
        return None
    nova = client.Client(version, username, password, tenant_id, auth_url)
    nova.client.tenant_id = tenant_id
    try:
        nova.authenticate()
    except Exception as e:
        print "Error: %s" %e
        return None
    return nova


def get_inventory(nova):
    if not nova:
        return {}
    inventory = {"_meta": {
                   "hostvars": {}
                 }}
    server_list = nova.servers.list()
    for s in server_list:
        ansible_host = s.id
        metadata = s.metadata
        address = s.networks[s.networks.keys()[0]][0]
        if 'ansible_groups' in s.metadata:
            for group in s.metadata['ansible_groups'].split(','):
                if group not in inventory:
                    inventory[group] = [ansible_host]
                else:
                    inventory[group].append(ansible_host)
            variables = {}
            # Take the first address as ansible_host by default.
            # If host has more than one addresses (e.g. multiple NICs,
            # Floating IP), then user should specify host address by
            # 'ansible_host' key in metadata
            variables['ansible_host'] = address
            variables['ansible_hostname'] = s.name
            for key, value in s.metadata.items():
                if key != 'ansible_groups':
                    variables[key] = value
            inventory["_meta"]["hostvars"][ansible_host] = variables
    return inventory


def main():
    nova = get_client()
    inventory = get_inventory(nova)
    print json.dumps(inventory, indent=2)


if __name__ == "__main__":
    main()
