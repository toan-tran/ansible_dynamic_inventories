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
# Set metadata to OpenStack's VMs based on an INI inventory file.
# After uploading metadata to VMs, the openstack_inventory can re-create
# an inventory directly from the platform.
#
# This script will also create a JSON template file based on the inventory
#
# Why need this script: In may case, the VMs are created from another machine
# than the Ansible (Uploader). Thus Ansible machine should not need to get the the
# inventory file from the former. The Uploader will maintain an inventory version
# and update the VMs whenerver the inventory is modified. The Ansible machine does
# not need to get the newly updated inventory file. It can dynamically get it 
# directly from the OpenStack platform.
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


def set_metadata(configs, inventory):
    "Set VM metadata based on an inventory"

    nova = get_client(configs)
    server_list = nova.servers.list()
    default_section = configs.get("Default", {})
    namespace = default_section.get("metadata_namespace",
                                    DEFAULT_METADATA_NAMESPACE)
    host_indicator = default_section.get("host_indicator", "id")
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
    parser = argparse.ArgumentParser(description='OpenStack upload metadata')
    parser.add_argument('-o', '--out-template', metavar='template', 
                        default=None,
                        help="Save the template of the inventory in a file")
    parser.add_argument('inventory', help="Inventory file (INI format)")
    parser.add_argument('-n', '--no-update', action='store_true',
                        help="If set, do not update metadata of the VMs")

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
    inventory = parse_inventory(filename)
    if args.out_template:
        print("Generating template file %s..." % args.out_template)
        template = make_template(inventory)
        with open(args.out_template, 'w') as f:
            json.dump(template, f, indent=2)
    if not args.no_update:
        print("Updating metadata...")
        set_metadata(configs, inventory)


if __name__ == "__main__":
    main()
