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

sys.path.insert(1, '..')

from ansible_dynamic_inventories.openstack_inventory_manager import OpenStackInventoryManager
from ansible_dynamic_inventories.utils.parse import get_config


def get_args():
    parser = argparse.ArgumentParser(description=
                        'Create VMs on OpenStack using an Ansible inventory')
    parser.add_argument('-c', '--config', metavar='config',
                        default=None,
                        help="Configuration file")
    parser.add_argument('-o', '--out-template', metavar='template',
                        default=None,
                        help="Save the template of the inventory in a file")
    parser.add_argument('-t', '--use-template',
                        action='store_true',
                        help="If set, will create a template file that "
                             "contains all inherited variables")
    parser.add_argument('-u', '--update',
                        action='store_true',
                        help="If set, will update the platform")

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
    configs = get_config(args.config)
    if args.use_template:
        configs["Default"]["no_template"] = True
    openstack_inventory = OpenStackInventoryManager(configs)
    openstack_inventory.update_platform(inherited=not args.use_template,
                                        inventory_file=args.inventory,
                                        update=args.update)
    if not args.update:
        print "If you are sure that the actions are correct, re-run the script with --update to update the platform."
    if args.out_template:
        print("Generating template file %s..." % args.out_template)
        template = make_template(openstack_inventory.inventory)
        with open(args.out_template, 'w') as f:
            json.dump(template, f, indent=2)


if __name__ == "__main__":
    main()
