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

from ConfigParser import ConfigParser
import os
import sys

from ansible.inventory.group import Group
from ansible.inventory.ini import InventoryParser
from novaclient import client

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
            parser = ConfigParser()
            configs = dict()
            parser.read(os.path.expanduser(cf))
            for sec in parser.sections():
                configs[sec] = dict(parser.items(sec))
            return configs
    return {}


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


def parse_inventory(filename):
    """Get an inventory from an INI file
    :param filename: filename
    :return: ansible.inventory.ini.InventoryParser
    Raise AnsibleError if file is not correctly formatted.
    """
    groups = {'ungrouped': Group('ungrouped'), 'all': Group('all')}
    inventory = InventoryParser(loader=None, groups=groups, filename=filename)
    return inventory


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
        

def main():
    if len(sys.argv) < 2:
        print "Usage: %s <inventory_filename>" % sys.argv[0]
        exit(0)
    filename = os.path.abspath(os.path.expanduser(sys.argv[1]))
    if not os.path.exists(filename):
        print "ERROR: File %s does not exists" % filename
        exit(0)
    if os.path.isfile(filename):
        print "ERROR: %s is not a file" % filename
        exit(0)
    configs = get_config()
    inventory = parse_inventory(filename)
    set_metadata(configs, inventory)


if __name__ == "__main__":
    main()
