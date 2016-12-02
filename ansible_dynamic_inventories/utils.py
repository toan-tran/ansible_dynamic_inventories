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
# OpenStack dynamic inventory for Ansible - Utils module
# This script will look for configuration file in the following order:
# .ansible/openstack_inventory.conf
# ~/ansible/openstack_inventory.conf
# /etc/ansible/openstack_inventory.conf
#

from ConfigParser import ConfigParser
import json
import os

from ansible.inventory.group import Group
from ansible.inventory.ini import InventoryParser
from novaclient import client

CONF_FILES = ["openstack_inventory.conf",
              ".ansible/openstack_inventory.conf",
              "~/.ansible/openstack_inventory.conf",
              "/etc/ansible/openstack_inventory.conf"]

HOST_INDICATORS = ["id", "name"]

DEFAULT_METADATA_NAMESPACE = "ansible:"

DEFAULT_KEY_FOLDER = "."


def get_config(filename=None):
    """Get configs from filename or known locations.
    If no file is present, no config is returned.
    :param filename: config filename. If no filename is present,
                     will search in known locations.
    :return: (dict) configs
             Empty dict if no file exists."""

    conf_files = []
    if filename:
        conf_files.append(filename)
    conf_files.extend(CONF_FILES)
    for cf in conf_files:
        if os.path.exists(os.path.expanduser(cf)):
            parser = ConfigParser()
            configs = dict()
            parser.read(os.path.expanduser(cf))
            for sec in parser.sections():
                configs[sec] = dict(parser.items(sec))
            print ("Found configuration file at: %s" % cf)
            return configs
    return {}


def get_template(configs):
    "Get inventory template from template file."
    inventory = {"_meta": {
                   "hostvars": {}
                 }}
    if "Template" in configs:
        if "template_file" in configs["Template"]:
            with open(os.path.abspath(os.path.expanduser(configs["Template"]["template_file"]))) as f:
                template = json.load(f)
                inventory.update(template)
    return inventory

    
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


def make_template(inventory):
    """Get a dictionary template from an inventory.
    The template will contain all hierarchical informations and variables of
    the groups, but not information of the hosts.
    :param inventory: ansible.inventory.ini.InventoryParser
    :return: (dict) a template of the inventory
    """
    template = {}
    groups = [g for g in inventory.groups.values() if g.child_groups or g.vars]
    for g in groups:
        # Special case: all. Only keep variables
        if g.name == 'all':
            if g.vars:
                template['all'] = {'vars': g.vars}
            continue
        # Special case: ungrouped. Ignore.
        if g.name == 'ungrouped':
            continue
        template[g.name] = {}
        if g.child_groups:
            template[g.name]['children'] = [cg.name for cg in g.child_groups]
        if g.vars:
            template[g.name]['vars'] = g.vars
    return template


def parse_inventory_file(filename):
    """Get an inventory from an INI file
    :param filename: filename
    :return: ansible.inventory.ini.InventoryParser
    Raise AnsibleError if file is not correctly formatted.
    """
    groups = {'ungrouped': Group('ungrouped'), 'all': Group('all')}
    inventory = InventoryParser(loader=None, groups=groups, filename=filename)
    return inventory
