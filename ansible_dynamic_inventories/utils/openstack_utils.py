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

import os
from time import sleep

from cinderclient import client as cclient
from novaclient import client as nclient

from ansible_dynamic_inventories.utils import *
from ansible_dynamic_inventories.utils import ansible_utils as au

OPENSTACK_VOLUME_PREFIX = "openstack_volume"


class ConfigError(Exception):
    pass


class VolumeAttachmentError(Exception):
    pass


class VolumeDeletingError(Exception):
    pass


class OpenStackVolume(object):
    def __init__(self, volume_id, host, device):
        self.volume_id = volume_id
        self.host = host
        self.device = device


class OpenStackClient(object):
    "Class for interact with OpenStack platform"

    def __init__(self, configs):
        """Initiate client.
        configs: (dict) key-value configuration
        """
        self.configs = configs
        self._validate_config()
        self.nova = None
        self.cinder = None

    def _validate_config(self):
        "Validate configs. Update configs with environment variables."

        authentication = self.configs.get('Authentication', {})
        os_version = os.environ.get('OS_VERSION',
                                    authentication.get('os_version',2))
        authentication['os_version'] = os_version

        os_auth_url = os.environ.get('OS_AUTH_URL',
                                     authentication.get('os_auth_url'))
        if not os_auth_url:
            raise Exception("ERROR: OS_AUTH_URL is not set")
        authentication['os_auth_url'] = os_auth_url

        os_username = os.environ.get('OS_USERNAME',
                                     authentication.get('os_username'))
        if not os_username:
            raise Exception("ERROR: OS_USERNAME is not set")
        authentication['os_username'] = os_username
        os_password = os.environ.get('OS_PASSWORD',
                                     authentication.get('os_password'))
        if not os_password:
            raise Exception("ERROR: OS_PASSWORD is not set")
        authentication['os_password'] = os_password

        os_tenant_id = os.environ.get('OS_TENANT_ID',
                                      authentication.get('os_tenant_id'))
        authentication['os_tenant_id'] = os_tenant_id

        os_tenant_name = os.environ.get('OS_TENANT_NAME',
                                        authentication.get('os_tenant_name'))
        authentication['os_tenant_name'] = os_tenant_name
        if not (os_tenant_id or os_tenant_name):
            raise ConfigError("Neither OS_TENANT_ID or OS_TENANT_NAME is set")

    def initiate_client(self):
        os_auth_url     = self.configs['Authentication']['os_auth_url']
        os_version      = self.configs['Authentication']['os_version']
        os_username     = self.configs['Authentication']['os_username']
        os_password     = self.configs['Authentication']['os_password']
        os_tenant_id    = self.configs['Authentication']['os_tenant_id']
        os_tenant_name  = self.configs['Authentication']['os_tenant_name']
        if os_tenant_id:
            self.nova = nclient.Client(os_version, os_username, os_password,
                                       tenant_id=os_tenant_id,
                                       auth_url=os_auth_url)
            self.cinder = cclient.Client(version=os_version,
                                         username=os_username,
                                         api_key=os_password,
                                         tenant_id=os_tenant_id,
                                         auth_url=os_auth_url)
        else:
            self.nova = nclient.Client(os_version, os_username, os_password,
                                       project_id=os_tenant_name,
                                       auth_url=os_auth_url)
            self.cinder = cclient.Client(version=os_version,
                                         username=os_username,
                                         api_key=os_password,
                                         project_id=os_tenant_name,
                                         auth_url=os_auth_url)
        # Authenticate client.
        # Raise exception as it is
        self.nova.authenticate()
        self.cinder.authenticate()

    def create_vm(self, host, metadata_namespace=DEFAULT_METADATA_NAMESPACE,
                  inherited=True):
        """Create a VM on an OpenStack platform based on an Ansible inventory host
        :param host: ansible.inventory.host.Host object
        :param inherited: (bool)(default) True if no template is used, all
                          inherited groups and variables will be stored in
                          host's metadata
                          False if a template is used, only host-specific
                          groups and variables will be stored in hosts' metadata
        :param return: new VM
        """
        host_vars = au.get_host_variables(host, inherited=True)
        if ("openstack_image_id" not in host_vars):
            raise Exception("ERROR: openstack_image_id is defined")
        if ("openstack_flavor_id" not in host_vars):
            raise Exception("ERROR: openstack_image_id is not defined")
        if ("openstack_network_id" not in host_vars):
            raise Exception("ERROR: openstack_network_id is not defined")
    
        # Get network ID
        # TODO: optimize this part to avoid multiple calls to OpenStack
        net_id = ''
        net_list = self.nova.networks.list()
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
        meta = au.create_host_metadata(host, metadata_namespace)
        print("Create VM: name=%-10s flavor=%-6s image=%-20s key_name=%-10s "
              "security_groups=%s nics=%s metadata=%s\n" %
              (name, flavor, image, key_name, security_groups, nics, meta))
        self.nova.servers.create(name, image, flavor, meta=meta,
                                 security_groups=security_groups,
                                 key_name=key_name, nics=nics)

    def delete_vm(self, vm):
        """Delete a VM from the OpenStack platform.
        :param vm: (novaclient.v2.servers.Server) server to delete
        """
        current_attached_volumes = self.nova.volumes.get_server_volumes(vm.id)
        # Detach volumes first. OpenStack detaches volume automatically
        # when deleting VMs, however, this is always better to avoid potential bugs
        for volume in current_attached_volumes:
            try:
                print("Detach volume %s from VM %s" % (volume.volumeId, vm.name))
                self.nova.volumes.delete_server_volume(vm.id, volume.id)
            except Exception as e:
                print("Warning: Detaching volume %s from VM %s: %s" % (volume.volumeId, vm.name,e))
        print("Delete VM %s" % vm.name)
        self.nova.servers.delete(vm)
        # Delete attached volumes
        for volume in current_attached_volumes:
            try:
                print("Delete volume: name=%-10s" % volume.volumeId)
                self.cinder.volumes.delete(volume.volumeId)
            except Exception as e:
                print("Warning: Deleting volume %s: %s" % (volume.volumeId, e))
    
    def update_metadata(self, vm, host, metadata_namespace, inherited=True):
        """Update metadata of the VM to match the correspondent host.
        :param host: (ansible.inventory.host.Host) Host declared in the inventory,
                     correspondent to the VM
        :param metadata_namespace: (string) namespace of the project
        :param inherited: (bool)(default) True if no template is used, all
                          inherited groups and variables will be stored in
                          host's metadata
                          False if a template is used, only host-specific
                          groups and variables will be stored in hosts' metadata
        """
        # Update VM's metadata
        meta = au.create_host_metadata(host, metadata_namespace,
                                         inherited=inherited)
        vm_meta = {}
        for key, value in vm.metadata.items():
            if key.startswith(metadata_namespace):
                vm_meta[key] = value
        if vm_meta != meta:
            print("Update VM metadata: name=%-10s metadata=%s\n" % (host.name, meta))
            self.nova.servers.delete_meta(vm, vm_meta.keys())
            self.nova.servers.set_meta(vm, metadata=meta)

    def delete_volume(self, volume):
        """Delete volume on OpenStack platform, detach volume if necessary.
        :param volume: (cinderclient.v2.volumes.Volume) volume, or
                       (string) ID of the volume
        """
        if isinstance(volume, (str, unicode)):
            volume = self.cinder.volumes.get(volume_id)
        for attachment in volume.attachments:
            print("Detaching volume %s from VM %s" % (volume.name, attachment["server_id"]))
            self.nova.volumes.delete_server_volume(attachment["server_id"], volume.id)
            sleep(5)
        print("Deleting volume %s" % volume.name)
        for i in range(5):
            try:
                self.cinder.volumes.delete(volume)
                break
            except Exception as e:
                if i==4:
                    print("Give up on deleting volume %s" % volume.name)
                    raise VolumeDeletingError(e)
                print("Warning: Volume is not ready to be deleted. %s." %e)
                print("Wait 20 seconds")
                sleep(20)

    def update_volumes(self, vm, host, metadata_namespace=DEFAULT_METADATA_NAMESPACE):
        """Create and attach volumes to VM following the description of a host
        in an inventory.
        Host volume must be described in host vars. Syntax: 
            <device_name>=<volume_size_GB>[,volume_type]
            e.g. vdb=10,standard
        This function will create a volume with name <vm_name>_<device_name> and
        attach to the vm as <device_name>
        Will not check wether the volume_type exists or not
        If the VM already has a volume attached to the current device, then change
        its name if necessary.
        If the VM a volume does not attach to any device listed in host var, then
        the volume will be deleted
        :param vm: VM to attach volumes to
        :param host: inventory host with description of volumes
        """
        expected_volumes = {}
        for key, value in au.get_host_variables(host, inherited=True).items():
            if key.startswith(OPENSTACK_VOLUME_PREFIX):
                device = key[len(OPENSTACK_VOLUME_PREFIX)+1:]
                expected_volumes[device] = str(value)
 
        current_attached_volumes = [self.cinder.volumes.get(vol.id) for vol in
                                    self.nova.volumes.get_server_volumes(vm.id)]
 
        for vol in current_attached_volumes:
            for attachment in vol.attachments:
                if attachment['server_id'] == vm.id:
                    device = attachment['device'].split('/')[-1]
                    if device not in expected_volumes:
                        print "Detach volume %s" % vol.name
                        self.nova.volumes.delete_server_volume(vm.id, vol.id)
                        sleep(3)
                        print "Delete volume %s" % vol.name
                        self.cinder.volumes.delete(vol)
                    else:
                        if vol.name != vm.name + '_' + device:
                            print "Change volume name"
                            self.cinder.volumes.update(vol, name=vm.name + '_' + device)
                        print "Remove volume from list"
                        expected_volumes.pop(device)
                    break
    
        for device, value in expected_volumes.items():
            vol_info = value.split(',')
            vol_size = int(vol_info[0])
            if len(vol_info) > 1:
                vol_type = vol_info[1]
            else:
                vol_type = None
            print "Create volume: Name: %s Size: %d Type: %s" % (vm.name + '_' + device, vol_size, vol_type)
            new_vol = self.cinder.volumes.create(vol_size,
                                                 name=vm.name + '_' + device,
                                                 volume_type=vol_type,
                                                 metadata = {metadata_namespace + "host": vm.name,
                                                             metadata_namespace + "device": device})
            print "Attach volume: %s to VM: %s as device: %s" % (new_vol.name, vm.name, device)
            for trial in range(5):
                try:
                    self.nova.volumes.create_server_volume(vm.id, new_vol.id, "/dev/" + device)
                    break
                except nclient.exceptions.Conflict as e:
                    print "Warning: %s" % e
                    if trial == 4:
                        print "Give up attahing volumes"
                        raise VolumeAttachmentError("Cannot attach volumes: %s" % e)
                    print "VM is not yet ready. Wait for 30 seconds"
                    sleep(30)
