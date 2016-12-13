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

import json
import os

from ansible.inventory.group import Group
from ansible.inventory.ini import InventoryParser


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


def get_host_groups(host, inherited=True):
    """Get all groups of the host. Will ignore 'ungrouped' and 'all'.
    :param host: ansible.inventory.host.Host object
    :param inherited: (bool)(default) True if no template is used, all
                      inherited groups and variables will be stored in
                      host's metadata
                      False if a template is used, only host-specific
                      groups and variables will be stored in hosts' metadata
    :return: list of (string) group names
    """
    if inherited:
        groups = host.get_groups()
    else:
        groups = host.groups
    return [gr.name for gr in groups if gr.name not in ['ungrouped', 'all']]


def get_host_variables(host, inherited=True):
    """Get all variables of the host and its groups
    :param host: ansible.inventory.host.Host object
    :param inherited: (bool) True if no template is used, all hierarchical
                      groups will be stored in hosts' metadata
                      False (default) if a template is used, only direct
                      groups will be stored in hosts' metadata
    :return: (dict) host variables as format key: value
    """
    if not inherited:
        return host.vars
    host_vars = host.get_group_vars()
    host_vars.update(host.vars)
    return host_vars


def create_host_metadata(host, metadata_namespace, inherited=True):
    """Create metadata correspondent to a host in an inventory.
    :param host: (ansible.inventory.host.Host) Host declared in the
                 Ansible inventory
    :param metadata_namespace: (string) namespace of the project
    :param inherited: (bool)(default) True if no template is used, all
                      inherited groups and variables will be stored in
                      host's metadata
                      False if a template is used, only host-specific
                      groups and variables will be stored in hosts' metadata
    :return: (dict) full metadata correspondent to the host's variables
    """
    meta = {}
    groups = get_host_groups(host, inherited=inherited)
    if groups:
        meta[metadata_namespace + "groups"] = ','.join(groups)
    else:
        meta[metadata_namespace + "groups"] = 'ungrouped'

    host_vars = get_host_variables(host, inherited=inherited)
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
