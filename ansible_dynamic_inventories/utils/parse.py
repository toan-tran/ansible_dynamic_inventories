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

from ConfigParser import ConfigParser
import json
import os

CONF_FILES = ["openstack_inventory.conf",
              ".ansible/openstack_inventory.conf",
              "~/.ansible/openstack_inventory.conf",
              "/etc/ansible/openstack_inventory.conf"]


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
