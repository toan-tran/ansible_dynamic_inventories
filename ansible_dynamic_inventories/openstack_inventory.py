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

import json
import os

from utils import *


def get_inventory(configs):
    """Generate an inventory from OpenStack platform.
    :param configs: (dict) Configuration
    :return: (dict) inventory
    """
    inventory = get_template(configs)
    nova = get_client(configs)
    if not nova:
        return {}
    server_list = nova.servers.list()
    default_section = configs.get("Default", {})
    namespace = default_section.get("metadata_namespace",
                                    DEFAULT_METADATA_NAMESPACE)
    key_folder = default_section.get("key_folder", DEFAULT_KEY_FOLDER)
    key_folder = os.path.abspath(os.path.expanduser(key_folder))

    for s in server_list:
        inventory_hostname = s.name
        metadata = s.metadata
        group_key = namespace + 'groups'
        address = s.networks[s.networks.keys()[0]][0]
        if group_key in s.metadata:
            for group in s.metadata[group_key].split(','):
                if group not in inventory:
                    inventory[group] = {"hosts": [inventory_hostname]}
                elif "hosts" not in inventory[group]:
                    inventory[group]["hosts"] = [inventory_hostname]
                else:
                    inventory[group]["hosts"].append(inventory_hostname)
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
            inventory["_meta"]["hostvars"][inventory_hostname] = variables
    return inventory


def main():
    configs = get_config()
    inventory = get_inventory(configs)
    print json.dumps(inventory, indent=2)


if __name__ == "__main__":
    main()
