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
# Create VMs on an OpenStack platform based on an INI inventory file.
# If the inventory file changes, re-running the script will update the
# platform.
# This script uses VMs' names as their indicator
#
# This script will look for configuration file in the following order:
# .ansible/openstack_inventory.conf
# ~/ansible/openstack_inventory.conf
# /etc/ansible/openstack_inventory.conf
#

import argparse
import os
import sys

from ansible.inventory.group import Group
from ansible.inventory.ini import InventoryParser

from utils import *


def validate_configs(configs):
    "Validate configs to create VMs"
    if "VirtualMachineInfo" not in configs:
        raise Exception('"VirtualMachineInfo" not found in config')
    if "image" not in configs["VirtualMachineInfo"]:
        raise Exception('"image" not found in "VirtualMachineInfo" config section')
    if "flavor" not in configs["VirtualMachineInfo"]:
        raise Exception('"flavor" not found in "VirtualMachineInfo" config section')
    if "net_id" not in configs["VirtualMachineInfo"]:
        raise Exception('"net_id" not found in "VirtualMachineInfo" config section')
    if "key_name" not in configs["VirtualMachineInfo"]:
        raise Exception('"key_name" not found in "VirtualMachineInfo" config section')
    if "security_groups" not in configs["VirtualMachineInfo"]:
        raise Exception('"security_groups" not found in "VirtualMachineInfo" config section')


def create_vms(configs, inventory):
    "Create VMs based on an inventory"
    client = get_client(configs)
    hosts = inventory.hosts.values()
    server_list = client.servers.list()
    default_section = configs.get("Default", {})
    namespace = default_section.get("metadata_namespace",
                                    DEFAULT_METADATA_NAMESPACE)
    groups_metadata = namespace + "groups"
    server_infos = {}
    for s in server_list:
        if groups_metadata in s.metadata:
            server_infos[s.name] = {'server': s, 'groups': s.metadata[groups_metadata], 'vars': {}}
    # Get all Inventory hosts that are not existed on OpenStack platform
    unmapped_inventory_hosts = [host for host in hosts
                                if host.name not in server_infos]
    for host in unmapped_inventory_hosts:
        _create_vm(client, host, namespace)


def _create_vm(client, host, metadata_namespace=DEFAULT_METADATA_NAMESPACE):
    """Create a VM based on an Ansible inventory host.
    :param client: novaclient.v2.client.Client object
    :param host: ansible.inventory.host.Host object
    """
    vm_info = {}
    vm_info.update(host.get_group_vars())
    vm_info.update(host.get_vars())
    if ("openstack_image_id" not in vm_info):
        raise Exception("ERROR: openstack_image_id is defined")
    if ("openstack_flavor_id" not in vm_info):
        raise Exception("ERROR: openstack_image_id is not defined")
    if ("openstack_network_id" not in vm_info):
        raise Exception("ERROR: openstack_network_id is not defined")

    name = host.name
    image = vm_info["openstack_image_id"]
    flavor = vm_info["openstack_flavor_id"]
    nics = [{"net-id": vm_info["openstack_network_id"],
             "v4-fixed-ip": host.address}]
    security_groups = vm_info.get("openstack_security_groups")
    if security_groups:
        security_groups = security_groups.split(",")
    if "ansible_private_key_file" in vm_info:
        key_name = os.path.basename(vm_info["ansible_private_key_file"])
    else:
        key_name = vm_info.get("openstack_keypair_id")
    # Update VM's metadata
    meta = {}
    groups = [gr.name for gr in host.groups if gr.name not in ['ungrouped', 'all']]
    if groups:
        meta[metadata_namespace + "groups"] = ','.join(groups)
    for key, value in host.vars.items():
        meta[metadata_namespace + key] = str(value)
    # Add "ansible_private_key_file" when openstack_keypair_id is used
    if "ansible_private_key_file" not in host.vars:
        meta[metadata_namespace + "ansible_private_key_file"] = key_name

    print("\nCreate VM: name=%-10s flavor=%-6s image=%-20s key_name=%-10s security_groups=%s nics=%s metadata=%s\n" %
          (name, flavor, image, key_name, security_groups, nics, meta))

    client.servers.create(name, image, flavor, meta=meta,
                          security_groups=security_groups,
                          key_name=key_name, nics=nics)


def _delete_vm(client, vm):
    "Delete VM"
    client.servers.delete(vm)


def update_metadata(configs, inventory):
    "Update VMs' metadata based on an inventory"

    nova = get_client(configs)
    server_list = nova.servers.list()
    default_section = configs.get("Default", {})
    namespace = default_section.get("metadata_namespace",
                                    DEFAULT_METADATA_NAMESPACE)
    host_indicator = default_section.get("host_indicator", "name")
    if host_indicator not in HOST_INDICATORS:
        raise Exception("ERROR: Invalid host_indicator")

    server_infos = {}
    for s in server_list:
        server_infos[getattr(s, host_indicator)] = {'server': s, 'groups': [], 'vars': {}}

    for hname, host in inventory.hosts.items():
        if hname not in server_infos:
            raise Exception("Host %s is not found on cloud." % hname)
        server_infos[hname]['vars'] = host.vars

    for gname, group in inventory.groups.items():
        for host in group.hosts:
            server_infos[host.name]['groups'].append(group.name)

    for indicator, info in server_infos.items():
        # If there is no group for this server, then it does not belong
        # to our playbook
        if not info['groups']:
            continue
        # Special case: Ansible add all hosts in an 'ungrouped' group
        # We need to remove all hosts that already have at least one group
        if (len(info['groups']) > 1) and ('ungrouped' in info['groups']):
            info['groups'].remove('ungrouped')
        meta = {}
        meta[namespace + "groups"] = ','.join(info['groups'])
        for key, value in info['vars'].items():
            meta[namespace + key] = str(value)
        nova.servers.set_meta(info['server'], meta)


def get_args():
    parser = argparse.ArgumentParser(description=
                        'Create VMs on OpenStack using an ANsible inventory')
    parser.add_argument('-o', '--out-template', metavar='template',
                        default=None,
                        help="Save the template of the inventory in a file")
    parser.add_argument('inventory', help="Inventory file (INI format)")
    args = parser.parse_args()
    filename = args.inventory
    if not os.path.exists(filename):
        print "ERROR: File %s does not exists" % filename
        exit(0)
    if not os.path.isfile(filename):
        print "ERROR: %s is not a file" % filename
        exit(0)
    return args


def main():
    args = get_args()
    filename = args.inventory
    configs = get_config()
    inventory = parse_inventory_file(filename)
    create_vms(configs, inventory)
    if args.out_template:
        print("Generating template file %s..." % args.out_template)
        template = make_template(inventory)
        with open(args.out_template, 'w') as f:
            json.dump(template, f, indent=2)


if __name__ == "__main__":
    main()
