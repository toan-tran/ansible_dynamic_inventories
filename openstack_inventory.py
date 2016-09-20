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
# This script will look for configuration file in the following order:
# .ansible/openstack_inventory.conf
# ~/ansible/openstack_inventory.conf
# /etc/ansible/openstack_inventory.conf
#

import ConfigParser
import json
from novaclient import client
import os

CONF_FILES = [".ansible/openstack_inventory.conf",
              "~/.ansible/openstack_inventory.conf",
              "/etc/ansible/openstack_inventory.conf"]

HOST_INDICATORS = ["id", "name"]


def get_config():
    """Get configs from known locations.
    If no file is present, no config is returned.
    :return: (dict) configs
             Empty dict if no file exists."""

    for cf in CONF_FILES:
        if os.path.exists(os.path.expanduser(cf)):
            parser = ConfigParser.ConfigParser()
            configs = dict()
            parser.read(os.path.expanduser(cf))
            for sec in parser.sections():
                configs[sec] = dict(parser.items(sec))
            return configs
    return {}


def get_template(configs):
    "Get inventory template from template file."
    inventory = {"_meta": {
                   "hostvars": {}
                 }}
    if "Template" in configs:
        if "template_file" in configs["Template"]:
            with open(os.path.expanduser(configs["Template"]["template_file"])) as f:
                template = json.load(f)
                inventory.update(template)
    return inventory

    
def get_client(configs):
    authentication = configs.get('Authentication', {})
    os_version = os.environ.get('OS_VERSION',
                                authentication.get('os_version',2))
    os_auth_url = os.environ.get('OS_AUTH_URL',
                                 authentication.get('os_auth_url'))
    if not os_auth_url:
        print "ERROR: OS_AUTH_URL is not set"
        return None
    os_username = os.environ.get('OS_USERNAME',
                                 authentication.get('os_username'))
    if not os_username:
        print "ERROR: OS_USERNAME is not set"
        return None
    os_password = os.environ.get('OS_PASSWORD',
                                 authentication.get('os_password'))
    if not os_password:
        print "ERROR: OS_PASSWORD is not set"
        return None
    os_tenant_id = os.environ.get('OS_TENANT_ID',
                                  authentication.get('os_tenant_id'))
    if not os_tenant_id:
        print "ERROR: OS_TENANT_ID is not set"
        return None
    nova = client.Client(os_version, os_username, os_password,
                         os_tenant_id, os_auth_url)
    nova.client.tenant_id = os_tenant_id
    try:
        nova.authenticate()
    except Exception as e:
        print "Error: %s" %e
        return None
    return nova


def get_inventory(configs):
    inventory = get_template(configs)
    nova = get_client(configs)
    if not nova:
        return {}
    server_list = nova.servers.list()
    host_indicator = configs.get("Default", {}).get("host_indicator", "id")
    if host_indicator not in HOST_INDICATORS:
        print "ERROR: Invalid host_indicator"
        return {}

    for s in server_list:
        ansible_host = getattr(s, host_indicator)
        metadata = s.metadata
        address = s.networks[s.networks.keys()[0]][0]
        if 'ansible_groups' in s.metadata:
            for group in s.metadata['ansible_groups'].split(','):
                if group not in inventory:
                    inventory[group] = {"hosts": [ansible_host]}
                elif "hosts" not in inventory[group]:
                    inventory[group]["hosts"] = [ansible_host]
                else:
                    inventory[group]["hosts"].append(ansible_host)
            variables = {}
            # Take the first address as ansible_host by default.
            # If host has more than one addresses (e.g. multiple NICs,
            # Floating IP), then user should specify host address by
            # 'ansible_host' key in metadata
            variables['ansible_host'] = address
            variables['ansible_hostname'] = s.name
            for key, value in s.metadata.items():
                if (key.startswith('ansible_') and (key != 'ansible_groups')):
                    variables[key] = value
            inventory["_meta"]["hostvars"][ansible_host] = variables
    return inventory


def main():
    configs = get_config()
    inventory = get_inventory(configs)
    print json.dumps(inventory, indent=2)


if __name__ == "__main__":
    main()
