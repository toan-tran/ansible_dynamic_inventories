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


class OpenStackInventory(object):

    def __init__(self, configs):
        """OpenStackInventory.
        :param configs: (dict) configuration content
        :param inventory: (ansible.inventory.ini.InventoryParser) Inventory object
        """
        self.configs = configs
        self.client = get_client(self.configs)

        
    def update_platform(self, inventory_file, inherited=False, update=False):
        """Synchronize the VMs based on an inventory.
        This function also deletes VMs if their names are no longer in the
        inventory.
        If inherited is True, only host-specific infos are stored in hosts'
        metadata. Other information, such as group variables, group hierarchy,
        will be store in a template. This template si necessary for
        openstack_inventory.py to reconstruct the entire inventory.
        If inherited is False, will save all variables, including group hierarchy
        and variables in the hosts' metadata. openstack_inventory.py will not need
        a template to reproduce the inventory. However, any change such as group
        variable values must be updated by this script.
        :param inventory_file: Inventory (INI) file
        :param inherited: (bool) True if no template is used, all inherited
                          variables will be stored in hosts' metadata
                          False (default) if a template is used, only host-specific
                          variables will be stored in hosts' metadata
        :param update: (bool) True: update the OpenStack platform
                       (default) False: only show actions, not update the platform
        """
        inventory = parse_inventory_file(inventory_file)
        host_list = inventory.hosts.values()
        vm_list = self.client.servers.list()
        if "openstack_namespace" in inventory.groups["all"].vars:
            namespace = self.inventory.groups["all"].vars["openstack_namespace"]
        else:
            default_section = self.configs.get("Default", {})
            namespace = default_section.get("metadata_namespace",
                                            DEFAULT_METADATA_NAMESPACE)
        groups_metadata = namespace + "groups"
        scoped_vms = {}
        for vm in vm_list:
            if groups_metadata in vm.metadata:
                scoped_vms[vm.name] = vm
        # Get all Inventory hosts that are not existed on OpenStack platform
        unmapped_inventory_hosts = [host for host in host_list
                                         if host.name not in scoped_vms]
        # Get all VMs that are no longer in inventory
        hostnames = [host.name for host in host_list]
        unmapped_vms = [scoped_vms[vm_name] for vm_name in scoped_vms
                                            if vm_name not in hostnames]
        # Get all VMs that are associated with hosts in the Inventory
        mapped_vms = [scoped_vms[vm_name] for vm_name in scoped_vms
                                          if vm_name in hostnames]
        if not update:
            print("Create VMs: %s" % unmapped_inventory_hosts)
            print("Delete VMs: %s" % unmapped_vms)
            print("Update metadata for VMs: %s" % mapped_vms)
            return
    
        for host in unmapped_inventory_hosts:
            self._create_vm(host, namespace, inherited=inherited)
    
        for vm in unmapped_vms:
            self._delete_vm(vm)
    
        for vm in mapped_vms:
            self._update_metadata(vm, inventory.hosts[vm.name],
                                  metadata_namespace=namespace,
                                  inherited=inherited)


    def _get_host_groups(self, host, inherited=False):
        """Get all groups of the host. Will ignore 'ungrouped' and 'all'.
        :param host: ansible.inventory.host.Host object
        :param inherited: (bool) True if no template is used, all hierarchical
                          groups will be stored in hosts' metadata
                          False (default) if a template is used, only direct
                          groups will be stored in hosts' metadata
        :return: list of (string) group names
        """
        if inherited:
            groups = host.get_groups()
        else:
            groups = host.groups
        return [gr.name for gr in groups if gr.name not in ['ungrouped', 'all']]
    
    
    def _create_vm(self, host, metadata_namespace=DEFAULT_METADATA_NAMESPACE,
                   inherited=False):
        """Create a VM based on an Ansible inventory host.
        :param host: ansible.inventory.host.Host object
        :param inherited: (bool) True if no template is used, all inherited groups
                          and variables will be stored in hosts' metadata
                          False (default) if a template is used, only host-specific
                          groups and variables will be stored in hosts' metadata
        """
        host_vars = self._get_host_variables(host, inherited=True)
        if ("openstack_image_id" not in host_vars):
            raise Exception("ERROR: openstack_image_id is defined")
        if ("openstack_flavor_id" not in host_vars):
            raise Exception("ERROR: openstack_image_id is not defined")
        if ("openstack_network_id" not in host_vars):
            raise Exception("ERROR: openstack_network_id is not defined")
    
        # Get network ID
        # TODO: optimize this part to avoid multiple calls to OpenStack
        net_id = ''
        net_list = self.client.networks.list()
        for net in net_list:
            if (net.id == host_vars["openstack_network_id"] or 
                net.label == host_vars["openstack_network_id"]):
                net_id = net.id
                break
        if not net_id:
            raise Exception("Network '%s' does not exists" %
                             host_vars["openstack_network_id"])
    
        name = host.name
        image = host_vars["openstack_image_id"]
        flavor = host_vars["openstack_flavor_id"]
        nics = [{"net-id": net_id,
                 "v4-fixed-ip": host.address}]
        security_groups = host_vars.get("openstack_security_groups")
        if security_groups:
            security_groups = security_groups.split(",")
        if "ansible_private_key_file" in host_vars:
            key_name = os.path.basename(host_vars["ansible_private_key_file"])
        else:
            key_name = host_vars.get("openstack_keypair_id")
        meta = self._create_host_metadata(host, metadata_namespace)
        print("Create VM: name=%-10s flavor=%-6s image=%-20s key_name=%-10s "
              "security_groups=%s nics=%s metadata=%s\n" %
              (name, flavor, image, key_name, security_groups, nics, meta))
        self.client.servers.create(name, image, flavor, meta=meta,
                                   security_groups=security_groups,
                                   key_name=key_name, nics=nics)
    
    
    def _delete_vm(self, vm):
        """Delete a VM from the OpenStack platform.
        :param vm: (novaclient.v2.servers.Server) server to delete
        """
        print("Delete VM: name=%-10s" % vm.name)
        self.client.servers.delete(vm)
    
    
    def _create_host_metadata(self, host, metadata_namespace, inherited=False):
        """Create metadata correspondent to a host in an inventory.
        :param host: (ansible.inventory.host.Host) Host declared in the
                     Ansible inventory
        :param metadata_namespace: (string) namespace of the project
        :param inherited: (bool) True if no template is used, all inherited groups
                          and variables will be stored in hosts' metadata
                          False (default) if a template is used, only host-specific
                          groups and variables will be stored in hosts' metadata
        :return: (dict) full metadata correspondent to the host's variables
        """
        meta = {}
        groups = self._get_host_groups(host, inherited=inherited)
        if groups:
            meta[metadata_namespace + "groups"] = ','.join(groups)
        else:
            meta[metadata_namespace + "groups"] = 'ungrouped'
    
        host_vars = self._get_host_variables(host, inherited=inherited)
        for key, value in host_vars.items():
            meta[metadata_namespace + key] = str(value)
        # Update "ansible_private_key_file" metadata
        if "ansible_private_key_file" in host_vars:
            key_name = os.path.basename(host_vars["ansible_private_key_file"])
        else:
            key_name = host_vars.get("openstack_keypair_id")
        if key_name:
            meta[metadata_namespace + "ansible_private_key_file"] = key_name
        return meta
    
    
    def _get_host_variables(self, host, inherited=False):
        """Get all variables of the host and its groups
        :param host: ansible.inventory.host.Host object
        :param inherited: (bool) True if no template is used, groups' variables
                          will also be stored in hosts' metadata
                          False (default) if a template is used, only host-specific
                          variables will be stored in hosts' metadata
        :return: (dict) host variables as format key: value
        """
        if not inherited:
            return host.vars
        host_vars = host.get_group_vars()
        host_vars.update(host.vars)
        return host_vars
    
    
    def _update_metadata(self, vm, host, metadata_namespace, inherited=False):
        """Update metadata of the VM to match the correspondent host.
        :param vm: (novaclient.v2.servers.Server) server to update
        :param host: (ansible.inventory.host.Host) Host declared in the inventory,
                     correspondent to the VM
        :param metadata_namespace: (string) namespace of the project
        :param inherited: (bool) True if no template is used, all inherited groups
                          and variables will be stored in hosts' metadata
                          False (default) if a template is used, only host-specific
                          groups and variables will be stored in hosts' metadata
        """
        # Update VM's metadata
        meta = self._create_host_metadata(host, metadata_namespace, inherited=inherited)
        vm_meta = {}
        for key, value in vm.metadata.items():
            if key.startswith(metadata_namespace):
                vm_meta[key] = value
        if vm_meta != meta:
            print("Update VM metadata: name=%-10s metadata=%s\n" % (host.name, meta))
            self.client.servers.delete_meta(vm, vm_meta.keys())
            self.client.servers.set_meta(vm, metadata=meta)


def get_args():
    parser = argparse.ArgumentParser(description=
                        'Create VMs on OpenStack using an ANsible inventory')
    parser.add_argument('-c', '--config', metavar='config',
                        default=None,
                        help="Configuration file")
    parser.add_argument('-o', '--out-template', metavar='template',
                        default=None,
                        help="Save the template of the inventory in a file")
    parser.add_argument('-n', '--no-template',
                        action='store_true',
                        help="If set, will not create a template file, but "
                             "save inherited variables in the hosts' metadata")
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
    if args.no_template:
        configs["Default"]["no_template"] = True
    openstack_inventory = OpenStackInventory(configs)
    openstack_inventory.update_platform(inherited=args.no_template,
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
