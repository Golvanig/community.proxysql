#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2017, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = '''
---
module: proxysql_galera_hostgroups
author: "Ben Mildren (@bmildren); Thierry Royer (@ekinops.com)"
short_description: Manages galera hostgroups using the proxysql admin
                   interface
description:
   - Each row in mysql_galera_hostgroups represent a pair of
     writer_hostgroup and reader_hostgroup. ProxySQL will monitor the value of
     read_only for all the servers in specified hostgroups, and based on the
     value of read_only will assign the server to the writer or reader
     hostgroups.
options:
  writer_hostgroup:
    description:
      - Id of the writer hostgroup.
    type: int
    required: True
  backup_writer_hostgroup:
    description:
      - Id of the writer hostgroup.
    type: int
    required: True
  reader_hostgroup:
    description:
      - Id of the reader hostgroup.
    type: int
    required: True
  offline_hostgroup:
    description:
      - Id of the reader hostgroup.
    type: int
    required: True
  active:
    description:
      - Id of the reader hostgroup.
    type: int
    required: True
  max_writers:
    description:
      - Id of the reader hostgroup.
    type: int
    required: True
  writer_is_also_reader:
    description:
      - Id of the reader hostgroup.
    type: int
    required: True
  max_transactions_behind:
    description:
      - Id of the reader hostgroup.
    type: int
    required: True
  comment:
    description:
      - Text field that can be used for any purposes defined by the user.
    type: str
    default: ""
  state:
    description:
      - When C(present) - adds the galera hostgroup, when C(absent) -
        removes the galera hostgroup.
    type: str
    choices: [ "present", "absent" ]
    default: present
extends_documentation_fragment:
- community.proxysql.proxysql.managing_config
- community.proxysql.proxysql.connectivity
notes:
- Supports C(check_mode).
'''

EXAMPLES = '''
---
# This example adds a galera hostgroup, it saves the mysql server config
# to disk, but avoids loading the mysql server config to runtime (this might be
# because several galera hostgroup are being added and the user wants to
# push the config to runtime in a single batch using the
# community.general.proxysql_manage_config module).  It uses supplied credentials
# to connect to the proxysql admin interface.

- name: Add a galera hostgroup
  community.proxysql.proxysql_galera_hostgroups:
    login_user: 'admin'
    login_password: 'admin'
    writer_hostgroup: 1
    reader_hostgroup: 2
    state: present
    load_to_runtime: False

# This example removes a galera hostgroup, saves the mysql server config
# to disk, and dynamically loads the mysql server config to runtime.  It uses
# credentials in a supplied config file to connect to the proxysql admin
# interface.

- name: Remove a galera hostgroup
  community.proxysql.proxysql_galera_hostgroups:
    config_file: '~/proxysql.cnf'
    writer_hostgroup: 3
    reader_hostgroup: 4
    state: absent
'''

RETURN = '''
stdout:
    description: The galera hostgroup modified or removed from proxysql.
    returned: On create/update will return the newly modified group, on delete
              it will return the deleted record.
    type: dict
    "sample": {
        "changed": true,
        "msg": "Added server to mysql_hosts",
        "galera_group": {
            "comment": "",
            "reader_hostgroup": "1",
            "writer_hostgroup": "2"
        },
        "state": "present"
    }
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.proxysql.plugins.module_utils.mysql import (
    mysql_connect,
    mysql_driver,
    proxysql_common_argument_spec,
    save_config_to_disk,
    load_config_to_runtime,
)
from ansible.module_utils._text import to_native

# ===========================================
# proxysql module specific support methods.
#


def perform_checks(module):
    if not module.params["writer_hostgroup"] >= 0:
        module.fail_json(
            msg="writer_hostgroup must be a integer greater than or equal to 0"
        )

    if module.params["reader_hostgroup"] < 0:
        module.fail_json(
            msg="reader_hostgroup must be an integer greater than or equal to 0"
        )

    if module.params["reader_hostgroup"] == module.params["writer_hostgroup"]:
        module.fail_json(
            msg="reader_hostgroup and writer_hostgroup must be different integer values")


class ProxySQLGaleraHostgroup(object):

    def __init__(self, module, version):
        self.state = module.params["state"]
        self.save_to_disk = module.params["save_to_disk"]
        self.load_to_runtime = module.params["load_to_runtime"]
        self.writer_hostgroup = module.params["writer_hostgroup"]
        self.backup_writer_hostgroup = module.params["backup_writer_hostgroup"]
        self.reader_hostgroup = module.params["reader_hostgroup"]
        self.offline_hostgroup = module.params["offline_hostgroup"]
        self.active = module.params["active"]
        self.max_writers = module.params["max_writers"]
        self.writer_is_also_reader = module.params["writer_is_also_reader"]
        self.max_transactions_behind = module.params["max_transactions_behind"]
        self.comment = module.params["comment"]
        self.check_mode = module.check_mode

    def check_galera_group_config(self, cursor, keys):
        query_string = \
            """SELECT count(*) AS `galera_groups`
               FROM mysql_galera_hostgroups
               WHERE writer_hostgroup = %s"""

        query_data = \
            [self.writer_hostgroup]

        cursor.execute(query_string, query_data)
        check_count = cursor.fetchone()
        return (int(check_count['galera_groups']) > 0)

    def get_galera_group_config(self, cursor):
        query_string = \
            """SELECT *
               FROM mysql_galera_hostgroups
               WHERE writer_hostgroup = %s"""

        query_data = \
            [self.writer_hostgroup]

        cursor.execute(query_string, query_data)
        galera_group = cursor.fetchone()
        return galera_group

    def create_galera_group_config(self, cursor):
        query_string = \
            """INSERT INTO mysql_galera_hostgroups (
               writer_hostgroup,
               backup_writer_hostgroup,
               reader_hostgroup,
               offline_hostgroup,
               active,
               max_writers,
               writer_is_also_reader,
               max_transactions_behind,
               comment)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""

        query_data = \
            [self.writer_hostgroup,
             self.backup_writer_hostgroup,
             self.reader_hostgroup,
             self.offline_hostgroup,
             self.active,
             self.max_writers,
             self.writer_is_also_reader,
             self.max_transactions_behind,
             self.comment or '']

        cursor.execute(query_string, query_data)

        return True

    def delete_galera_group_config(self, cursor):
        query_string = \
            """DELETE FROM mysql_galera_hostgroups
               WHERE writer_hostgroup = %s"""

        query_data = \
            [self.writer_hostgroup]

        cursor.execute(query_string, query_data)
        return True

    def manage_config(self, cursor, state):
        if state and not self.check_mode:
            if self.save_to_disk:
                save_config_to_disk(cursor, "SERVERS")
            if self.load_to_runtime:
                load_config_to_runtime(cursor, "SERVERS")

    def create_galera_group(self, result, cursor):
        if not self.check_mode:
            result['changed'] = \
                self.create_galera_group_config(cursor)
            result['msg'] = "Added server to mysql_hosts"
            result['galera_group'] = \
                self.get_galera_group_config(cursor)
            self.manage_config(cursor,
                               result['changed'])
        else:
            result['changed'] = True
            result['msg'] = ("Galera group would have been added to" +
                             " mysql_galera_hostgroups, however" +
                             " check_mode is enabled.")

    def update_galera_group(self, result, cursor):
        current = self.get_galera_group_config(cursor)

        if current.get('comment') != self.comment:
            result['changed'] = True
            result['msg'] = "Updated galera hostgroups in check_mode"
            if not self.check_mode:
                result['msg'] = "Updated galera hostgroups"
                self.update_comment(cursor)

        if int(current.get('reader_hostgroup')) != self.reader_hostgroup:
            result['changed'] = True
            result['msg'] = "Updated galera hostgroups in check_mode"
            if not self.check_mode:
                result['msg'] = "Updated galera hostgroups"
                self.update_reader_hostgroup(cursor)

        result['galera_group'] = self.get_galera_group_config(cursor)

        self.manage_config(cursor,
                           result['changed'])

    def delete_galera_group(self, result, cursor):
        if not self.check_mode:
            result['galera_group'] = \
                self.get_galera_group_config(cursor)
            result['changed'] = \
                self.delete_galera_group_config(cursor)
            result['msg'] = "Deleted server from mysql_hosts"
            self.manage_config(cursor,
                               result['changed'])
        else:
            result['changed'] = True
            result['msg'] = ("Galera group would have been deleted from" +
                             " mysql_galera_hostgroups, however" +
                             " check_mode is enabled.")

    def update_reader_hostgroup(self, cursor):
        query_string = ("UPDATE mysql_galera_hostgroups "
                        "SET reader_hostgroup = %s "
                        "WHERE writer_hostgroup = %s")

        cursor.execute(query_string, (self.reader_hostgroup, self.writer_hostgroup))

    def update_comment(self, cursor):
        query_string = ("UPDATE mysql_galera_hostgroups "
                        "SET comment = %s "
                        "WHERE writer_hostgroup = %s ")

        cursor.execute(query_string, (self.comment, self.writer_hostgroup))


# ===========================================
# Module execution.
#
def main():
    argument_spec = proxysql_common_argument_spec()
    argument_spec.update(
        writer_hostgroup=dict(required=True, type='int'),
        backup_writer_hostgroup=dict(required=True, type='int'),
        reader_hostgroup=dict(required=True, type='int'),
        offline_hostgroup=dict(required=True, type='int'),
        active=dict(required=True, type='int'),
        max_writers=dict(required=True, type='int'),
        writer_is_also_reader=dict(required=True, type='int'),
        max_transactions_behind=dict(required=True, type='int'),
        comment=dict(type='str', default=''),
        state=dict(default='present', choices=['present',
                                               'absent']),
        save_to_disk=dict(default=True, type='bool'),
        load_to_runtime=dict(default=True, type='bool')
    )

    module = AnsibleModule(
        supports_check_mode=True,
        argument_spec=argument_spec
    )

    perform_checks(module)

    login_user = module.params["login_user"]
    login_password = module.params["login_password"]
    config_file = module.params["config_file"]

    cursor = None
    try:
        cursor, db_conn, version = mysql_connect(module,
                                                 login_user,
                                                 login_password,
                                                 config_file,
                                                 cursor_class='DictCursor')
    except mysql_driver.Error as e:
        module.fail_json(
            msg="unable to connect to ProxySQL Admin Module.. %s" % to_native(e)
        )

    proxysql_galera_group = ProxySQLGaleraHostgroup(module, version)
    result = {}

    result['state'] = proxysql_galera_group.state
    result['changed'] = False

    if proxysql_galera_group.state == "present":
        try:
            if not proxysql_galera_group.check_galera_group_config(cursor,
                                                               keys=True):
                proxysql_galera_group.create_galera_group(result,
                                                      cursor)
            else:
                proxysql_galera_group.update_galera_group(result, cursor)

                result['galera_group'] = proxysql_galera_group.get_galera_group_config(cursor)

        except mysql_driver.Error as e:
            module.fail_json(
                msg="unable to modify galera hostgroup.. %s" % to_native(e)
            )

    elif proxysql_galera_group.state == "absent":
        try:
            if proxysql_galera_group.check_galera_group_config(cursor,
                                                           keys=True):
                proxysql_galera_group.delete_galera_group(result, cursor)
            else:
                result['changed'] = False
                result['msg'] = ("The galera group is already absent from the" +
                                 " mysql_galera_hostgroups memory" +
                                 " configuration")

        except mysql_driver.Error as e:
            module.fail_json(
                msg="unable to delete galera hostgroup.. %s" % to_native(e)
            )

    module.exit_json(**result)


if __name__ == '__main__':
    main()
