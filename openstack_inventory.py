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

DEFAULT_METADATA_NAMESPACE = "ansible:"

DEFAULT_KEY_FOLDER = "."

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
            with open(os.path.abspath(os.path.expanduser(configs["Template"]["template_file"]))) as f:
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
        raise Exception("ERROR: OS_AUTH_URL is not set")
    os_username = os.environ.get('OS_USERNAME',
                                 authentication.get('os_username'))
    if not os_username:
        raise Exception("ERROR: OS_USERNAME is not set")
    os_password = os.environ.get('OS_PASSWORD',
                                 authentication.get('os_password'))
    if not os_password:
        raise Exception("ERROR: OS_PASSWORD is not set")
    os_tenant_id = os.environ.get('OS_TENANT_ID',
                                  authentication.get('os_tenant_id'))
    if not os_tenant_id:
        raise Exception("ERROR: OS_TENANT_ID is not set")
    nova = client.Client(os_version, os_username, os_password,
                         os_tenant_id, os_auth_url)
    nova.client.tenant_id = os_tenant_id

    # Authenticate client.
    # Raise exception as it is
    nova.authenticate()
    return nova


def get_inventory(configs):
    inventory = get_template(configs)
    nova = get_client(configs)
    if not nova:
        return {}
    server_list = nova.servers.list()
    default_section = configs.get("Default", {})
    host_indicator = default_section.get("host_indicator", "id")
    namespace = default_section.get("metadata_namespace",
                                    DEFAULT_METADATA_NAMESPACE)
    key_folder = default_section.get("key_folder", DEFAULT_KEY_FOLDER)
    key_folder = os.path.abspath(os.path.expanduser(key_folder))
    if host_indicator not in HOST_INDICATORS:
        raise Exception("ERROR: Invalid host_indicator")

    for s in server_list:
        ansible_host = getattr(s, host_indicator)
        metadata = s.metadata
        group_key = namespace + 'groups'
        address = s.networks[s.networks.keys()[0]][0]
        if group_key in s.metadata:
            for group in s.metadata[group_key].split(','):
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
            # '<metadata_namespace>:ansible_host' key in metadata
            variables['ansible_host'] = address
            variables['ansible_hostname'] = s.name
            for key, value in metadata.items():
                if key == (namespace + "ansible_private_key_file"):
                    variables["ansible_private_key_file"] = os.path.join(key_folder, value)
                elif (key.startswith(namespace) and (key != group_key)):
                    keyname = key[len(namespace):]
                    variables[keyname] = value
            inventory["_meta"]["hostvars"][ansible_host] = variables
    return inventory


def main():
    configs = get_config()
    inventory = get_inventory(configs)
    print json.dumps(inventory, indent=2)


if __name__ == "__main__":
    main()
