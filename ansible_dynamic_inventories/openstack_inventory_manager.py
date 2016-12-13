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
from utils import ansible_utils as au
from utils import openstack_utils as ou


class OpenStackInventoryManager(object):

    def __init__(self, configs):
        """OpenStackInventory.
        :param configs: (dict) configuration content
        :param inventory: (ansible.inventory.ini.InventoryParser) Inventory object
        """
        self.configs = configs
        self.client = ou.OpenStackClient(configs)
        self.client.initiate_client()

    def update_platform(self, inventory_file, inherited=True, update=False):
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
        inventory = au.parse_inventory_file(inventory_file)
        hostnames = inventory.hosts.keys()
        host_list = inventory.hosts.values()
        if "openstack_namespace" in inventory.groups["all"].vars:
            namespace = self.inventory.groups["all"].vars["openstack_namespace"]
        else:
            default_section = self.configs.get("Default", {})
            namespace = default_section.get("metadata_namespace",
                                            DEFAULT_METADATA_NAMESPACE)
        print "Namspace: %s" % namespace
        groups_metadata = namespace + "groups"
        vm_list = self.client.nova.servers.list()
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

        # Volumes listed in the Inventory
        inventory_volumes = {}
        for host in host_list:
            host_vars = au.get_host_variables(host, inherited=True)
            for key, value in host_vars.items():
                if key.startswith(ou.OPENSTACK_VOLUME_PREFIX):
                    device = key[len(ou.OPENSTACK_VOLUME_PREFIX)+1:]
                    inventory_volumes[host.name + '_' + device] = [host.name + '_' + device, host.name, device, value]
        # Volumes on OpenStack platform that belong to our namespace
        volume_list = self.client.cinder.volumes.list()
        scoped_volumes = {}
        volume_host_metadata = namespace + "host"
        for vol in volume_list:
            if volume_host_metadata in vol.metadata:
                scoped_volumes[vol.name] = {'host': vol.metadata[volume_host_metadata],
                                            'device': vol.metadata.get(namespace + "device"),
                                            'volume': vol}

        unmapped_inventory_volumes = {}
        for inv_vol_name, inv_vol in inventory_volumes.items():
            if inv_vol_name not in scoped_volumes:
                unmapped_inventory_volumes[inv_vol_name] = inv_vol
        unmapped_os_volumes = [scoped_volumes[vol_name]
                                    for vol_name in scoped_volumes
                                    if vol_name not in inventory_volumes]

        if not update:
            print("Create VMs: %s" % unmapped_inventory_hosts)
            print("Delete VMs: %s" % unmapped_vms)
            print("Update metadata for VMs: %s" % mapped_vms)
            print("Create volumes: %s" % unmapped_inventory_volumes)
            print("Delete volumes: %s" % [vol['volume'].name for vol in unmapped_os_volumes])
            return
    
        for host in unmapped_inventory_hosts:
            self._create_vm(host, metadata_namespace=namespace, inherited=inherited)
    
        for vm in unmapped_vms:
            self._delete_vm(vm)

        for vm in mapped_vms:
            self.client.update_metadata(vm, inventory.hosts[vm.name], metadata_namespace=namespace)

        for vol in unmapped_os_volumes:
            self._delete_volume(vol['volume'])    

        # Refresh the list of VMs
        vm_list = self.client.nova.servers.list()
        scoped_vms = {}
        for vm in vm_list:
            if vm.name in inventory.hosts and groups_metadata in vm.metadata:
                scoped_vms[vm.name] = vm
        for vm_name, vm in scoped_vms.items():
            self._update_volumes(vm, inventory.hosts[vm_name], namespace)

        print("OpenStackInventoryManager: update platform done")

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
        self.client.create_vm(host, metadata_namespace, inherited)

    def _delete_vm(self, vm):
        """Delete a VM from the OpenStack platform.
        :param vm: (novaclient.v2.servers.Server) server to delete
        """
        self.client.delete_vm(vm)

    def _update_metadata(self, vm, host, metadata_namespace=DEFAULT_METADATA_NAMESPACE, inherited=True):
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
        self.client.update_metadata(vm, host, metadata_namespace, inherited)

    def _delete_volume(self, volume):
        """Delete a volume from the OpenStack platform.
        :param volume: (cinderclient.v2.volumes.Volume) volume to delete
        """
        self.client.delete_volume(volume)
    
    def _update_volumes(self, vm, host, metadata_namespace=DEFAULT_METADATA_NAMESPACE):
        """Create and attach volumes to VM following the description of a host
        in an inventory.
        :param vm: VM to attach volumes to
        :param host: inventory host with description of volumes
        """
        self.client.update_volumes(vm, host, metadata_namespace=metadata_namespace)
