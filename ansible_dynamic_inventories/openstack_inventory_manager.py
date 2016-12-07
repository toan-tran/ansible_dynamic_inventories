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

from utils import *
from utils import ansible_utils as a
from utils import openstack_utils as o


class OpenStackInventoryManager(object):

    def __init__(self, configs):
        """OpenStackInventory.
        :param configs: (dict) configuration content
        :param inventory: (ansible.inventory.ini.InventoryParser) Inventory object
        """
        self.configs = configs
        self.nova = o.get_novaclient(configs)
        self.cinder = o.get_cinderclient(configs)

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
        inventory = a.parse_inventory_file(inventory_file)
        hostnames = inventory.hosts.keys()
        host_list = inventory.hosts.values()
        if "openstack_namespace" in inventory.groups["all"].vars:
            namespace = self.inventory.groups["all"].vars["openstack_namespace"]
        else:
            default_section = self.configs.get("Default", {})
            namespace = default_section.get("metadata_namespace",
                                            DEFAULT_METADATA_NAMESPACE)
        groups_metadata = namespace + "groups"
        vm_list = self.nova.servers.list()
        scoped_vms = {}
        for vm in vm_list:
            if groups_metadata in vm.metadata:
                scoped_vms[vm.name] = vm
        # Get all Inventory hosts that are not existed on OpenStack platform
        unmapped_inventory_hosts = [host for host in host_list
                                         if host.name not in scoped_vms]
       # Get all VMs that are no longer in inventory
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

        # Refresh the list of VMs
        vm_list = self.nova.servers.list()
        scoped_vms = {}
        for vm in vm_list:
            if vm_name in inventory.hosts and groups_metadata in vm.metadata:
                scoped_vms[vm.name] = vm
        for vm_name, vm in scoped_vms.items():
            self._update_volumes(vm, inventory.hosts[vm_name])

    def _create_vm(self, host, metadata_namespace=DEFAULT_METADATA_NAMESPACE,
                   inherited=False):
        """Create a VM based on an Ansible inventory host.
        :param host: ansible.inventory.host.Host object
        :param inherited: (bool) True if no template is used, all inherited groups
                          and variables will be stored in hosts' metadata
                          False (default) if a template is used, only host-specific
                          groups and variables will be stored in hosts' metadata
        :param return: new vm
        """
        o.create_vm(self.nova, host, metadata_namespace, inherited)

    def _delete_vm(self, vm):
        """Delete a VM from the OpenStack platform.
        :param vm: (novaclient.v2.servers.Server) server to delete
        """
        o.delete_vm(self.nova, vm)

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
        o.update_metadata(self.nova, vm, host, metadata_namespace, inherited)

    def _update_volumes(self, vm, host):
        """Create and attach volumes to VM following the description of a host
        in an inventory.
        :param vm: VM to attach volumes to
        :param host: inventory host with description of volumes
        """
        o.update_volumes(self.cinder, vm, host)
