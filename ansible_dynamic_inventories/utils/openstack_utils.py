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

from cinderclient import client as cclient
from novaclient import client as nclient

from ansible_dynamic_inventories.utils import *
from ansible_dynamic_inventories.utils.ansible_utils import *

OPENSTACK_VOLUME_PREFIX = "openstack_volume"


def get_novaclient(configs):
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
    os_tenant_name = os.environ.get('OS_TENANT_NAME',
                                    authentication.get('os_tenant_name'))
    if not (os_tenant_id or os_tenant_name):
        raise Exception("Neither OS_TENANT_ID or OS_TENANT_NAME is set")
    if os_tenant_id:
        nova = nclient.Client(os_version, os_username, os_password,
                              tenant_id=os_tenant_id, auth_url=os_auth_url)
    else:
        nova = nclient.Client(os_version, os_username, os_password,
                              project_id=os_tenant_name, auth_url=os_auth_url)
    # Authenticate client.
    # Raise exception as it is
    nova.authenticate()
    return nova


def get_cinderclient(configs):
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
    os_tenant_name = os.environ.get('OS_TENANT_NAME',
                                    authentication.get('os_tenant_name'))
    if not (os_tenant_id or os_tenant_name):
        raise Exception("Neither OS_TENANT_ID or OS_TENANT_NAME is set")
    if os_tenant_id:
        cinder = cclient.Client(version=os_version, username=os_username,
                                api_key=os_password, tenant_id=os_tenant_id,
                                auth_url=os_auth_url)
    else:
        cinder = cclient.Client(version=os_version, username=os_username,
                                api_key=os_password, project_id=os_tenant_name,
                                auth_url=os_auth_url)
    cinder.authenticate()
    return cinder


def create_vm(nova, host, metadata_namespace=DEFAULT_METADATA_NAMESPACE,
               inherited=False):
    """Create a VM on an OpenStack platform based on an Ansible inventory host
    :param nova: (novaclient.v2.client.Client) authenticated nova client
    :param host: ansible.inventory.host.Host object
    :param inherited: (bool) True if no template is used, all inherited groups
                      and variables will be stored in hosts' metadata
                      False (default) if a template is used, only host-specific
                      groups and variables will be stored in hosts' metadata
    :param return: new VM
    """
    host_vars = get_host_variables(host, inherited=True)
    if ("openstack_image_id" not in host_vars):
        raise Exception("ERROR: openstack_image_id is defined")
    if ("openstack_flavor_id" not in host_vars):
        raise Exception("ERROR: openstack_image_id is not defined")
    if ("openstack_network_id" not in host_vars):
        raise Exception("ERROR: openstack_network_id is not defined")

    # Get network ID
    # TODO: optimize this part to avoid multiple calls to OpenStack
    net_id = ''
    net_list = nova.networks.list()
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
    meta = create_host_metadata(host, metadata_namespace)
    print("Create VM: name=%-10s flavor=%-6s image=%-20s key_name=%-10s "
          "security_groups=%s nics=%s metadata=%s\n" %
          (name, flavor, image, key_name, security_groups, nics, meta))
    nova.servers.create(name, image, flavor, meta=meta,
                        security_groups=security_groups,
                        key_name=key_name, nics=nics)


def delete_vm(nova, vm):
    """Delete a VM from the OpenStack platform.
    :param nova: (novaclient.v2.client.Client) authenticated nova client
    :param vm: (novaclient.v2.servers.Server) server to delete
    """
    print("Delete VM: name=%-10s" % vm.name)
    nova.servers.delete(vm)


def update_metadata(nova, vm, host, metadata_namespace, inherited=False):
    """Update metadata of the VM to match the correspondent host.
    :param nova: (novaclient.v2.client.Client) authenticated nova client
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
    meta = create_host_metadata(host, metadata_namespace, inherited=inherited)
    vm_meta = {}
    for key, value in vm.metadata.items():
        if key.startswith(metadata_namespace):
            vm_meta[key] = value
    if vm_meta != meta:
        print("Update VM metadata: name=%-10s metadata=%s\n" % (host.name, meta))
        nova.servers.delete_meta(vm, vm_meta.keys())
        nova.servers.set_meta(vm, metadata=meta)


def update_volumes(cinder, vm, host):
    """Create and attach volumes to VM following the description of a host
    in an inventory. 
    :param cinder: (cinderclient.v2.client.Client) authenticated cinder client
    :param vm: VM to attach volumes to
    :param host: inventory host with description of volumes
    """
    volumes = {}
    for key, value in get_host_variables(host, inherited=True).items():
        if key.startswith(OPENSTACK_VOLUME_PREFIX):
            volumes[key[len(OPENSTACK_VOLUME_PREFIX)+1:]] = int(value)
