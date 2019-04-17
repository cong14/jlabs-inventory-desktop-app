# Authors: Campbell Ong, Victoria Pruim, Joshua Stattel, Kyle Gallun, Christina Rogers, Tommy Yost
#
# !!!!!REMEMBER TO UPDATE DATE AND VERSION!!!!!
#
# Date:  8/9/18
# Version: 1.9.9
#
# Purpose: GUI for inventory system
import kivy
kivy.require("1.9.0")
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.treeview import TreeView, TreeViewNode
from kivy.uix.label import Label
from kivy.properties import ObjectProperty
from kivy.uix.checkbox import CheckBox
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.behaviors.compoundselection import CompoundSelectionBehavior
from kivy.uix.button import Button
from kivy.core.window import Window
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from functools import partial
from kivy.uix.togglebutton import ToggleButton
import csv
import collections
import copy
import mysql.connector
import os
from kivy.config import Config
from popups import *

Config.set('graphics', 'minimum_width', '1500')
Config.set('graphics', 'width', '1500')
Config.set('graphics', 'minimum_height', '900')
Config.set('graphics', 'height', '900')
Config.set('kivy', 'exit_on_escape', '0')
Config.write()

# ############################################ KIVY SECTION ############################################################
Builder.load_file('layout.kv')
sm = ScreenManager()

# ######################################### GLOBAL VARIABLES ###########################################################
# Global lists used in printReport and possibly elsewhere
report_jlabs = []
report_names = []
report_fields = []
report_owners = []
own = []
report_owner_info = []
the_machine_owner = []
# ################################################ BEGIN SQL  #########################################################


def set_user_privs(username):
    # Dictionary holding all of test database's tables (minus TestSchema) as keys and their column names as strings in a list
    global test_schema
    test_schema = {}

    # User restrictions and privileges in dictionaries with all of test database's tables (minus TestSchema) as
    #  keys and their respectively restricted and permissible column names as strings in a list
    #  (for Kivy layout-formatting use)
    global restrictions_list
    restrictions_list = {}
    global privileges_list
    privileges_list = {}

    # User privileges dictionary with all of test database's tables (minus TestSchema) as keys and their permissible
    #  column names as a single comma-delimited string
    #  (for MySQL query use)
    global privileges_strings
    privileges_strings = {}

    # Global string holding user's role, by which their restrictions are retrieved
    global user_role
    user_role = ""

    # Get current user's role
    cur.execute("SELECT role from users where user = \"{}\"".format(username))
    user_role = str(cur.fetchone()[0])

    # Get current user's restricted columns
    cur.execute("SELECT tablename, columnname from restricted where role = \"{}\"".format(user_role))
    rows = list(cur.fetchall())

    if len(rows) > 0:
        for row in rows:
            if str(row[0]) in restrictions_list.keys():
                restrictions_list[str(row[0])].insert(0, str(row[1]))
            else:
                restrictions_list[str(row[0])] = []
                restrictions_list[str(row[0])].insert(0, str(row[1]))

    # Get the layout of the database and store in test_schema
    cur.execute("SHOW TABLES")
    rows = cur.fetchall()

    for row in rows:
        if str(row[0]) != "restricted" and str(row[0]) != "roles" and str(row[0]) != "users":
            test_schema[str(row[0])] = get_columns(str(row[0]))

    # test_schema - restrictions_list = privileges_list
    privileges_list = copy.deepcopy(test_schema)

    for key in privileges_list.keys():
        if key in restrictions_list.keys():
            for item in restrictions_list[key]:
                privileges_list[key].remove(item)

    for key in privileges_list.keys():
        privileges_strings[key] = ""
        for item in privileges_list[key]:
            privileges_strings[key] += item + ","

        privileges_strings[key] = privileges_strings[key][:-1]
    return


def null_user_restrictions(tname, row):
    global test_schema
    global restrictions_list

    missing_indices = []
    curr_table = copy.deepcopy(test_schema[tname])
    try:
        ures = copy.deepcopy(restrictions_list[tname])
        for col in ures:
            missing_indices.append(curr_table.index(col))
        for index in missing_indices:
            row.insert(index, "RESTRICTED")
        return row, missing_indices
    except:
        return row, []


def populate_jlab_buttons():
    """SQL: queries database and returns list of jlab_number fields from JLabs table"""
    jlab_list = []
    conn.row_factory = lambda cursor, row: row[0]
    cur = conn.cursor(buffered=True)
    cur.execute("SELECT jlab_number "
                "FROM jlabs "
                "ORDER BY jlab_number")
    rows = list(cur.fetchall())
    for row in rows:
        for num in row:
            jlab_list.append(num)
    return jlab_list


def get_fks(table_name):
    """SQL: identifies foreign keys on Hardware table (i.e. which attributes should be parents
    in the treeview and from which table to get its children) and saves attribute name to
    foreign keys list
    :return: foreign keys list"""
    fk_list = []
    cur.execute(
        "SELECT COLUMN_NAME "
        "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
        "WHERE TABLE_NAME = \"{}\" AND REFERENCED_TABLE_NAME IS NOT NULL;".format(
            table_name))
    rows = cur.fetchall()
    for row in rows:
        for col_name in row:
            fk_list.append(col_name)
    return fk_list


def get_fk_tables(table_name):
    """SQL: identifies foreign keys on Hardware table (i.e. which attributes should be parents
    in the treeview and from which table to get its children) and saves attribute name to
    foreign keys list
    :return: foreign keys list"""
    fk_tables = []
    cur.execute(
        "SELECT REFERENCED_TABLE_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE WHERE TABLE_NAME = \"{}\" AND "
        "REFERENCED_TABLE_NAME IS NOT NULL;".format(table_name))
    rows = cur.fetchall()
    for row in rows:
        for t_name in row:
            fk_tables.append(t_name)
    return fk_tables


def get_columns(table_name):
    """
    get column names of table and save as list
    :param table_name: table to be queried
    :return: list of column names
    """
    col_names = []
    cur.execute("SHOW COLUMNS FROM {}".format(table_name.lower()))
    # cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = \"{}\"".format(table_name))
    rows = cur.fetchall()
    for row in rows:
        col_names.append(str(row[0]))
    return col_names


def get_m_code(m_name):
    cur.execute("SELECT machine_code FROM machine WHERE machine_name = \"{}\";".format(m_name))
    m_code = int(cur.fetchone()[0])
    return m_code

# ################################################### END SQL #########################################################
# ###############################################  BEGIN POPUPS #######################################################

# EMPTY POPUPS - no python methods, layout and function defined in the .kv file - defined in popup.py file ############


# NOT EMPTY POPUPS - layout defined in kivy file, but they also have functions in python  #############################
# owner popups
class OwnerPopup(Popup):
    """
    popup for selecting, editing, and creating new owners
    used on Lookup and Add Screens
    """
    jlab = None
    machine = None
    mach = False

    def addOwnerProgram(self):
        """
        calls popup
        :return: None
        """
        own = []
        self.popup = AddOwnerPopup()
        self.popup.get_machine(self.machine, self.mach)
        if self.mach == False:
            self.popup.change()
        self.popup.open()

    def changeNameProgram(self):
        """
        changes text listed as owner info on two screens: lookup and link
        creates warning popup if not owner info is selected
        :return:None
        """
        try:
            for rlist in report_owners:
                if report_owner_info[0] == rlist[0]:
                    try:
                        # ADD NEW JLAB SCREEN
                        newText = \
                            self.parent.children[1].children[0].children[0].children[1].children[0].children[
                                0].children[2]
                        newText.text = rlist[0]
                        newText = \
                            self.parent.children[1].children[0].children[0].children[1].children[0].children[
                                0].children[1]
                        newText.text = rlist[1]
                        newText = \
                            self.parent.children[1].children[0].children[0].children[1].children[0].children[
                                0].children[0]
                        newText.text = rlist[2]
                    except IndexError:
                        # LOOKUP SCREEN
                        if self.mach == False:
                            cur.execute("SELECT owner_code FROM owner WHERE owner_name='{}'".format(str(rlist[0])))
                            o_code = cur.fetchone()[0]
                            cur.execute('select owner_code from jlabs where jlab_number = {}'.format(report_jlabs[0]))
                            old_owner_code = cur.fetchone()[0]
                            cur.execute("UPDATE jlabs "
                                        "SET owner_code={} "
                                        "WHERE jlab_number={};".format(o_code, report_jlabs[0]))
                            conn.commit()
                            # TRACK HISTORY report_jlabs[0] owner was changed from old_owner_code to o_code
                            self.parent.children[1].children[0].children[1].children[0].children[3].children[2].text = \
                                rlist[0]
                            self.parent.children[1].children[0].children[1].children[0].children[3].children[1].text = \
                                rlist[1]
                            self.parent.children[1].children[0].children[1].children[0].children[3].children[0].text = \
                                rlist[2]  # Alert user of successful user change
                            self.popup = Popup()
                            self.popup.title = "Success!"
                            self.popup.content = Label(text="JLab {}\'s Owner changed to\n{} in database."
                                                       .format(report_jlabs[0], rlist[0]),
                                                       halign='center')
                            self.popup.size = (250, 100)
                            self.popup.size_hint = (None, None)
                            self.popup.auto_dismiss = True
                            self.popup.open()
                        else:
                            self.popup = MachineOwnerPopup()
                            self.popup.get_new(rlist, self.machine)
                            self.popup.open()
            self.wipe()

        except IndexError:
            self.popup = SelOwner()
            self.popup.open()

    def editOwner(self, g):
        """once changes are made to an owner, change info on screen and in DB using the AddOwner popup"""
        global privileges_strings
        if report_owner_info != []:
            cur.execute("SELECT * FROM owner WHERE owner_name = \"{}\" ".format(report_owner_info[0]))
            o_rows = cur.fetchall()
            for row in o_rows:
                currRow = []
                for i in range(len(row)):
                    if i == 0:
                        currRow.append(row[0])
                    elif row[i] is None:
                        # Change None's to empty strings for GUI display
                        currRow.append('')
                    else:
                        currRow.append(str(row[i]))
                own.insert(0, currRow)
            self.popup = AddOwnerPopup()
            self.popup.get_machine(self.machine, self.mach)
            self.popup.children[0].children[0].children[0].children[0].children[1].text = "Save & Select"
            self.popup.open()
            self.dismiss()
        else:
            self.popup = EmptyOwner()
            self.popup.open()

    def noOwner(self):
        """set owner to NONE in database and on the screens"""
        if self.mach == False:
            if self.jlab != None:
                cur.execute('select owner_code from jlabs where jlab_number = {}'.format(self.jlab))
                old_owner_code = cur.fetchone()[0]
                cur.execute("UPDATE jlabs SET owner_code = NULL WHERE jlab_number = {}".format(self.jlab))
                conn.commit()
            try:
                # ADD NEW JLAB SCREEN
                newText = self.parent.children[1].children[0].children[0].children[1].children[0].children[0].children[
                    2]
                newText.text = ''

                newText = self.parent.children[1].children[0].children[0].children[1].children[0].children[0].children[
                    1]
                newText.text = ''

                newText = self.parent.children[1].children[0].children[0].children[1].children[0].children[0].children[
                    0]
                newText.text = ''
            except IndexError:
                # LOOK UP SCREEN
                self.parent.children[1].children[0].children[1].children[0].children[3].children[2].text = ''
                self.parent.children[1].children[0].children[1].children[0].children[3].children[1].text = ''
                self.parent.children[1].children[0].children[1].children[0].children[3].children[0].text = ''
        else:
            self.popup = MachineOwnerPopup()
            self.popup.get_new([None, None, None], None)
            self.popup.open()
        self.wipe()

    def getJLab(self, n):
        self.jlab = n

    def wipe(self):
        del report_owner_info[:]

    def get_machine(self, m):
        self.machine = m
        self.mach = True

    def filterOwners(self):
        """lookup owners by beginning to type their name, list will filter down on owner selectable grid"""
        grid = self.children[0].children[0].children[0].children[6].children[0]
        n_list = []
        grid.clear_widgets()
        del report_owners[:]
        mysqlCode = "SELECT * FROM owner WHERE owner_name LIKE '%"
        mysqlCode += self.children[0].children[0].children[0].children[7].children[1].text
        mysqlCode += "%'"
        cur.execute(mysqlCode)
        rows = cur.fetchall()
        for row in rows:
            currRow = []
            for i in range(1, len(row)):
                currRow.append(str(row[i]))
            report_owners.append(currRow)

        for row in report_owners:
            btn = Button(text=row[0],
                         id=("id" + row[0]))
            btn.size_hint = (1, None)
            btn.height = 50
            grid.add_widget(btn)
        return grid


class OwnerPopup2(Popup):
    """
    Popup for selecting a new owner
    used on Advanced Lookup screen
    """
    box = None
    mach = False
    mach_code = None

    def ChangeNameProgram(self):
        """change the name written on the screen """
        for rlist in report_owners:
            if report_owner_info[0] == rlist[0]:
                if self.mach == False:
                    # ADVANCED LOOKUP SCREEN
                    self.parent.children[1].children[0].children[1].children[0].children[0].children[3].children[
                        0].children[0].children[0].text = rlist[2]
                    self.parent.children[1].children[0].children[1].children[0].children[0].children[3].children[
                        0].children[0].children[1].text = rlist[1]
                    self.parent.children[1].children[0].children[1].children[0].children[0].children[3].children[
                        0].children[0].children[2].text = rlist[0]
                else:
                    self.box.children[0].children[0].text = rlist[0]
        del report_owners[:]

    def noOwner(self):
        """set owner info to None on the screen """
        # ADVANCED LOOKUP SCREEN
        self.parent.children[1].children[0].children[1].children[0].children[0].children[2].children[0].children[
            0].children[0].text = 'None'
        self.parent.children[1].children[0].children[1].children[0].children[0].children[2].children[0].children[
            0].children[1].text = 'None'
        self.parent.children[1].children[0].children[1].children[0].children[0].children[2].children[0].children[
            0].children[2].text = 'None'

    def get_machine(self, box, mach):
        self.box = box
        self.mach = mach

    def wipe(self):
        del report_owner_info[:]

    def filterOwners(self):
        """filter down search on owner selectable grid by beggining to type their name"""
        grid = self.children[0].children[0].children[0].children[4].children[0]
        n_list = []
        grid.clear_widgets()
        del report_owners[:]
        mysqlCode = "SELECT * FROM owner WHERE owner_name LIKE '%"
        mysqlCode += self.children[0].children[0].children[0].children[5].children[1].text
        mysqlCode += "%'"
        cur.execute(mysqlCode)
        rows = cur.fetchall()
        for row in rows:
            currRow = []
            for i in range(1, len(row)):
                currRow.append(str(row[i]))
            report_owners.append(currRow)

        for row in report_owners:
            btn = Button(text=row[0],
                         id=("id" + row[0]))
            btn.size_hint = (1, None)
            btn.height = 50
            grid.add_widget(btn)
        return grid


class AddOwnerPopup(Popup):
    """popup comes after OwnerPopup in order to promp info from user and create a new owner in the DB"""
    machine = None
    mach = False
    def createLayout(self, box):
        """method to fetch Owner labels from Owner columns in db and create text fields to fill in and create a new Owner
        :param: box: the current boy layout"""
        self.the_box = box
        # Get labels from db
        o_labels = get_columns("owner")
        del o_labels[0]
        for i in range(len(o_labels)):
            if o_labels[i] in dbDict:
                o_labels[i] = dbDict[o_labels[i]]
        b = BoxLayout(orientation='horizontal')
        for i in range(len(o_labels)):
            b.add_widget(Label(text=o_labels[i]))
            if own == []:
                b.add_widget(TextInput(write_tab=False, multiline=False))
            else:
                if (own[0][i + 1]) is None:
                    b.add_widget(TextInput(write_tab=False, text='', multiline=False))
                else:
                    b.add_widget(TextInput(write_tab=False, text=str(own[0][i + 1]), multiline=False))
            box.add_widget(b)
            if i < len(o_labels) - 1:
                b = BoxLayout(orientation='horizontal')

    def change(self):
        self.the_box.clear_widgets()
        o_labels = get_columns("owner")
        del o_labels[0]
        for i in range(len(o_labels)):
            if o_labels[i] in dbDict:
                o_labels[i] = dbDict[o_labels[i]]
        b = BoxLayout(orientation='horizontal')
        for i in range(len(o_labels)):
            b.add_widget(Label(text=o_labels[i]))
            b.add_widget(TextInput(write_tab=False, multiline=False))
            self.the_box.add_widget(b)
            if i < len(o_labels) - 1:
                b = BoxLayout(orientation='horizontal')

    def useInputs(self, g):
        """
        gets text inputs from user, creates a new owner in the DB and writes the new owner to the original screen
        :param g: boxlayout with owner info
        :return: None
        """
        global privileges_strings

        if self.no_quot_ao():
            the_list = []
            for i in range(3):
                the_list.append(
                    str(self.children[0].children[0].children[0].children[1].children[0].children[i].children[0].text))
            the_list.reverse()
            # if the user entered info for the new owner
            if len(the_list[0]) > 0:
                # if there is a new owner
                if own == []:
                    # Write new owner info to db
                    cur.execute("SELECT {} from owner".format(privileges_strings["owner"]))
                    owns = list(cur.fetchall())
                    # Get lowest available owner_code
                    o_codes_list = []
                    x = -1
                    for row in owns:
                        o_codes_list.append(int(row[0]))
                    x = len(o_codes_list) + 1
                    # insert new Owner
                    add_owner_query = "INSERT INTO owner VALUES({}".format(x)
                    for i in range(len(the_list)):
                        if the_list[i] == '':
                            add_owner_query = add_owner_query + ", NULL".format(the_list[i])
                        else:
                            add_owner_query = add_owner_query + ", \"{}\"".format(str(the_list[i]))
                    # if you are changing a jlab owner instead of machine owner
                    if self.mach == False:
                        try:
                            cur.execute(add_owner_query + ")")
                            conn.commit()
                            self.dismiss()
                            self.popup = Popup()
                            self.popup.title = "Success!"
                            d_msg1 = "{} added to Owners in database.".format(the_list[0])
                            self.popup.size_hint = (None, None)
                            scr_name = self.parent.children[1].children[0].name
                            if scr_name == 'lookup':
                                jlbn = int(report_jlabs[0])
                                cur.execute('update jlabs set owner_code = {} where jlab_number = {};'.format(x, jlbn))
                                conn.commit()
                                self.parent.children[1].children[0].children[1].children[0].children[3].children[
                                    2].text = the_list[0]
                                self.parent.children[1].children[0].children[1].children[0].children[3].children[
                                    1].text = the_list[1]
                                self.parent.children[1].children[0].children[1].children[0].children[3].children[
                                    0].text = the_list[2]
                            else:
                                # ADD SCREEN
                                self.popup.content = Label(text=d_msg1, halign='center')
                                self.popup.size = (len(d_msg1) * 9, 170)
                            self.popup.auto_dismiss = True
                            self.popup.open()
                        except mysql.connector.DatabaseError as e:
                            self.popup = ErrorPopup()
                            self.popup.size = (len(str(e)) * 8, 100)
                            self.popup.content = Label(text=str(e))
                            self.popup.auto_dismiss = True
                            self.popup.open()
                            self.new_mach_info = []
                    # changing machine owner
                    else:
                        cur.execute(add_owner_query + ")")
                        conn.commit()
                        self.dismiss()
                        self.popup = MachineOwnerPopup()
                        self.popup.get_new(the_list, None)
                        self.popup.open()
                else:
                    # Check that changes were made
                    if the_list == own[0][1:]:
                        self.popup = Popup()
                        self.popup.title = "Note:"
                        self.popup.content = Label(text="No changes were made.\n\nUser will not be selected.",
                                                   halign='center')
                        self.popup.size = (250, 150)
                        self.popup.size_hint = (None, None)
                        self.popup.auto_dismiss = True
                        self.popup.open()
                    else:
                        # Update owner info
                        code = own[0][0]
                        # Attempt to update owner in db
                        cur.execute("START TRANSACTION;")
                        o_errlist = []
                        # else, update user's value
                        for j in range(len(the_list)):
                            if own[0][j + 1] != the_list[j]:
                                try:
                                    if the_list[j] == '':
                                        cur.execute("UPDATE owner "
                                                    "SET {} = NULL "
                                                    "WHERE owner_code = {}".format(self.o_switch(j), code))
                                    else:
                                        cur.execute("UPDATE owner "
                                                    "SET {} = \"{}\" "
                                                    "WHERE owner_code = {}".format(self.o_switch(j),
                                                                                   str(the_list[j]).replace(
                                                                                       "'", "''"), code))
                                except mysql.connector.errors.IntegrityError as e:
                                    o_errlist.append(str(e))
                        # If changes are acceptable, save to db and tell user
                        if len(o_errlist) == 0:
                            conn.commit()
                            self.clearInputs(g)
                            self.dismiss()
                            # Use ErrorPopup Class to tell user of successful changes
                            self.popup = ErrorPopup()
                            self.popup.size = (200, 165)
                            self.popup.title = "Success!"
                            self.popup.children[0].children[0].children[0].children[1].text = \
                                "Owner info updated in database.\n"
                            self.popup.open()
                            if self.mach == False:
                                try:
                                    # REFRESH OWNER TEXTINPUTS IF OWNER EDITED IS CURRENT JLAB'S OWNER
                                    cur.execute(
                                        "SELECT owner_code FROM jlabs WHERE jlab_number = {}".format(report_jlabs[0]))
                                    row = cur.fetchone()

                                    for j_code in row:
                                        curr_jlab_ocode = int(j_code)

                                    if curr_jlab_ocode == code:
                                        currScreen = self.parent.children[1].parent.children[2].children[0]
                                        if currScreen.name == 'lookup':
                                            o_lookup = currScreen.children[1].children[0].children[3]
                                            o_lookup.children[2].text = the_list[0]
                                            o_lookup.children[1].text = the_list[1]
                                            o_lookup.children[0].text = the_list[2]
                                        elif currScreen.name == 'add':
                                            o_add = currScreen.children[0].children[1].children[0].children[0]
                                            o_add.children[2].text = the_list[0]
                                            o_add.children[1].text = the_list[1]
                                            o_add.children[0].text = the_list[2]
                                        else:
                                            pass
                                except:
                                    currScreen = self.parent.children[1].parent.children[2].children[0]
                                    if currScreen.name == 'add':
                                        o_add = currScreen.children[0].children[1].children[0].children[0]
                                        o_add.children[2].text = the_list[0]
                                        o_add.children[1].text = the_list[1]
                                        o_add.children[0].text = the_list[2]
                            else:
                                self.popup = MachineOwnerPopup()
                                self.popup.get_new(the_list, self.machine)
                                self.popup.open()

                            # If changes result in error(s), undo and tell user
                        else:
                            cur.execute("ROLLBACK;")
                            err_msg = ""
                            for i in range(len(o_errlist)):
                                err_msg += "{}) {}\n".format(i + 1, o_errlist[i])

                            self.popup = OwnerScrollPopup()
                            self.popup.children[0].children[0].children[0].children[0].children[0].text = err_msg
                            self.popup.open()
            else:
                self.popup = EmptyOwner()
                self.popup.open()
            del report_owner_info[:]
        else:
            self.popup = ErrorQuotesPopup()
            self.popup.children[0].children[0].children[0].children[0].text = "Check Owner fields."
            self.popup.open()

    def no_quot_ao(self):
        no_quot = True

        for i in range(3):
            if '"' in str(
                    self.children[0].children[0].children[0].children[1].children[0].children[i].children[0].text):
                no_quot = False

        return no_quot

    def clearInputs(self, g):
        """clears inputs in the popup"""
        for i in g.children:
            i.children[0].text = ''

    def o_switch(self, index):
        """
        makes a switch statement from Machine table (minus machine_code) to be used in write_changes() to identify
        which Machine field(s) have been changed...returns column name of changed field(s)
        :param arg: index (in both list and switch) of changed field
        :return: column name of changed field
        """
        o_columns = get_columns("owner")
        del o_columns[0]
        switch = {}
        for i in range(len(o_columns)):
            switch[i] = o_columns[i]
        return switch.get(index, "nothing")

    def wipe(self):
        del report_owner_info[:]

    def get_machine(self, m, ma):
        self.machine = m
        self.mach = ma


class MachineOwnerPopup(Popup):
    contact = None
    machine = None

    def get_info(self, c, m):
        self.contact = c
        self.machine = m
        the_machine_owner.append(m)
        if self.machine is not None:
            cur.execute("select m_owner_code from machine where machine_code = {}".format(self.machine))
            m_code = cur.fetchone()[0]
            if m_code is not None:
                cur.execute('select * from owner where owner_code = {}'.format(m_code))
                owner = list(cur.fetchone())
                for i in range(len(owner)):
                    if owner[i] == None:
                        owner[i] = ''
            else:
                owner = [0, "", "", ""]
        else:
            owner = [0, "", "", ""]
        self.children[0].children[0].children[0].children[3].children[0].text = owner[1]
        self.children[0].children[0].children[0].children[2].children[0].text = owner[2]
        self.children[0].children[0].children[0].children[1].children[0].text = owner[3]

    def get_new(self, olist, machine):
        self.machine = machine
        if olist[0] != None:
            self.children[0].children[0].children[0].children[3].children[0].text = olist[0]
            self.children[0].children[0].children[0].children[2].children[0].text = olist[1]
            self.children[0].children[0].children[0].children[1].children[0].text = olist[2]
            cur.execute("select * from owner where owner_name = '{}'".format(olist[0]))
            owner = cur.fetchone()[0]
            if self.machine is not None:
                cur.execute('update machine set m_owner_code = {} where machine_code = {}'.format(owner, self.machine))
                conn.commit()
            else:
                cur.execute('update machine set m_owner_code = {} where machine_code is NULL'.format(owner))
                conn.commit()
        else:
            self.children[0].children[0].children[0].children[3].children[0].text = ''
            self.children[0].children[0].children[0].children[2].children[0].text = ''
            self.children[0].children[0].children[0].children[1].children[0].text = ''
            cur.execute('update machine set m_owner_code = NULL where machine_code = {}'.format(the_machine_owner[0]))
            conn.commit()
        the_machine_owner[:]

    def edit_contact(self):
        self.popup = OwnerPopup()
        self.popup.get_machine(self.machine)
        self.popup.open()
        self.dismiss()


# other popups
class SaveDialog(Popup):
    srchd_table = ""
    srchd = []
    rprt_fields = []
    rprt_jlabs = []

    def __init__(self, my_widget, **kwargs):  # my_widget is now the object where popup was called from.
        super(SaveDialog, self).__init__(**kwargs)

        self.my_widget = my_widget

    def upload(self, file_chosen, chosen_fp):
        try:
            global chosen_filepath
            chosen_filepath = str(file_chosen.selection[0])

            chosen_fp.text = chosen_filepath
        except IndexError:
            self.popup = ErrorPopup()
            self.popup.content = Label(text="Please select a file.")
            self.popup.size_hint = (None, None)
            self.popup.size = (175, 100)
            self.popup.open()

    def save(self, path, filename):
        # Only begin the saving process if correct file format
        if not filename.endswith(".csv"):
            popup = CsvErrorPopup()
            popup.open()
        else:
            global privileges_strings
            global test_schema

            if len(self.srchd) > 0:
                try:
                    if self.srchd_table == 'jlabs':
                        # change everything in jlabels over to nice names from dictionary
                        jLa = copy.deepcopy(test_schema[self.srchd_table])

                        jLabels = []
                        for i in jLa:
                            if dbDict[i] == 'Owner Info:':
                                jLabels.append('Owner')
                            else:
                                jLabels.append(dbDict[i])

                        self.srchd.insert(0, jLabels)

                        # Insert "RESTRICTED" value(s) in each row
                        for i in range(1, len(self.srchd)):
                            self.srchd[i] = null_user_restrictions(self.srchd_table, list(self.srchd[i]))[0]

                        # switch owner code to owner name
                        for i in range(1, len(self.srchd)):
                            try:
                                cur.execute(
                                    "select {} from owner where owner_code = {}".format(privileges_strings["owner"],
                                                                                        int(self.srchd[i][4])))
                                owner = cur.fetchone()
                                self.srchd[i][4] = str(owner[1])
                            except TypeError:
                                self.srchd[i][4] = ''

                        with open(os.path.join(path, filename), "wb") as csv_file:
                            cw = csv.writer(csv_file)
                            for i in self.srchd:
                                cw.writerow(i)

                    elif self.srchd_table == 'machine':
                        # get names of labels from dbdict, add labels to beginning of file
                        mLa = copy.deepcopy(test_schema[self.srchd_table])
                        mLabels = []
                        for i in mLa:
                            mLabels.append(dbDict[i])
                        self.srchd.insert(0, mLabels)

                        # Insert "RESTRICTED" value(s) in each row
                        for i in range(1, len(self.srchd)):
                            self.srchd[i] = null_user_restrictions(self.srchd_table, list(self.srchd[i]))[0]

                        with open(os.path.join(path, filename), "wb") as csv_file:
                            cw = csv.writer(csv_file)
                            for i in self.srchd:
                                cw.writerow(i[1:])

                    self.dismiss()
                    popup = FileCreatedPopup()
                    popup.open()

                except AttributeError:
                    # stops from crashing if user hits cancel
                    pass
            else:
                try:
                    file_msg = []
                    # # "Translate" fields in report_names back to database attribute names
                    dbDict_vals = list(dbDict.values())
                    dbDict_keys = list(dbDict.keys())

                    old_rep_names = copy.copy(report_names)
                    r_n = []
                    for i in dbDict_vals:
                        if i in report_names:
                            r_n.append(i)
                    # always include jlab number, never include headers from tree sections
                    r_n.insert(0, 'JLab #')
                    if 'Machine(s) Info:' in r_n:
                        r_n.remove('Machine(s) Info:')
                    if 'Owner Info:' in r_n:
                        r_n.remove('Owner Info:')

                    # switch from dictionary names to sql names
                    for name in r_n:
                        if name in dbDict_vals:
                            index = dbDict_vals.index(name)
                            report_fields.append(dbDict_keys[index])

                    if 'Machine Owner' in r_n:
                        i = report_names.index('Machine Owner')
                        r_n.remove('Machine Owner')
                        r_n.insert(i, 'Contact Name')
                        r_n.insert(i + 1, 'Contact Email')
                        r_n.insert(i + 2, 'Contact Phone')

                    # all fields selected on screen
                    file_msg.append(r_n)

                    # all jlabs selected on screen
                    j_labels = get_columns('jlabs')

                    machine_codes = []

                    if self.parent.children[1].children[0].ids['unattached_btn'].state == 'down':
                        report_jlabs.append(None)
                    # get machines from selected jlab
                    for lab in report_jlabs:
                        selected_j_info = []
                        if lab != None:
                            lab = int(lab)
                            cur.execute("select * from hardware where jlab_number = {}".format(lab))
                            links = cur.fetchall()
                            machine_codes = []
                            for i in links:
                                machine_codes.append(i[1])
                            cur.execute("select * from jlabs where jlab_number = {}".format(lab))
                            labs = cur.fetchall()
                            jlabDict = {}
                            for all in labs:
                                for field in range(len(all)):
                                    if j_labels[field] == 'owner_code':
                                        try:
                                            cur.execute('select * from owner where owner_code = {}'.format(all[field]))
                                            owner = cur.fetchone()
                                        except:
                                            owner = ['', '', '', '']
                                        jlabDict['owner_name'] = str(owner[1])
                                        jlabDict['owner_email'] = str(owner[2])
                                        jlabDict['owner_phone'] = str(owner[3])
                                    else:
                                        if all[field] == 'NULL' or all[field] == None:
                                            jlabDict[j_labels[field]] = ''
                                        else:
                                            jlabDict[j_labels[field]] = str(all[field])
                            j_labels.append('owner_name')
                            j_labels.append('owner_email')
                            j_labels.append('owner_phone')

                            for i in report_fields:
                                if i in j_labels:
                                    selected_j_info.append(jlabDict[i])
                        else:
                            spaces = len(selected_j_info)
                            selected_j_info = []
                            machine_codes = []
                            cur.execute(
                                "SELECT machine_code FROM machine WHERE machine_code NOT IN(SELECT machine_code FROM hardware)")
                            row = cur.fetchall()
                            for i in row:
                                machine_codes.append(i[0])
                        # create dictionary with all machine fields and their values
                        m_labels = get_columns('machine')
                        sel_m = []
                        if len(machine_codes) > 0:
                            for code in machine_codes:
                                cur.execute("select * from machine where machine_code = {}".format(code))
                                machine_list = cur.fetchall()
                                for machine in machine_list:
                                    machines = {}
                                    for all in range(len(machine)):
                                        if m_labels[all] == 'm_owner_code':
                                            if machine[all] is not None:
                                                cur.execute(
                                                    'select * from owner where owner_code = {}'.format(machine[all]))
                                                owner = cur.fetchone()
                                            else:
                                                owner = ['', '', '', '']
                                            jlabDict['contact_name'] = str(owner[1])
                                            jlabDict['contact_email'] = str(owner[2])
                                            jlabDict['contact_phone'] = str(owner[3])
                                        else:
                                            if machine[all] == 'NULL' or machine[all] == None:
                                                machines[m_labels[all]] = ''
                                            else:
                                                machines[m_labels[all]] = str(machine[all])
                                # get slected info from the list of machines that are selected
                                selectedInfo = []
                                m_labels.append('contact')
                                for field in report_fields:
                                    # if contact info selected, append contact info
                                    if field == 'm_owner_code':
                                        selectedInfo.append(jlabDict['contact_name'])
                                        selectedInfo.append(jlabDict['contact_email'])
                                        selectedInfo.append(jlabDict['contact_phone'])
                                    elif field in m_labels:
                                        selectedInfo.append(machines[field])
                                # each row contains jlab info and then machine info
                                if lab == None:
                                    s_j_info = []
                                    s_j_info.append('N/A')
                                    for i in range(spaces - 1):
                                        s_j_info.append(' ')
                                    sel_row = s_j_info + selectedInfo
                                else:
                                    sel_row = selected_j_info + selectedInfo
                                sel_m.append(sel_row)
                        else:
                            sel_m.append(selected_j_info)
                        for i in sel_m:
                            file_msg.append(i)
                        # put empty line between jlabs
                        file_msg.append([])

                    with open(os.path.join(path, filename), "wb") as csv_file:
                        cw = csv.writer(csv_file)
                        for line in file_msg:
                            cw.writerow(line)

                    # get ready to read in next machine or jlab
                    # delete info from temorary variables
                    del report_names[:]
                    for i in old_rep_names:
                        report_names.append(i)
                    if None in report_jlabs:
                        report_jlabs.remove(None)
                    del selected_j_info[:]
                    try:
                        del selectedInfo[:]
                    except UnboundLocalError:
                        pass
                        #no machine info to be deleted
                    del report_fields[:]
                    self.dismiss()
                    # let user know that the file was created
                    popup = FileCreatedPopup()
                    popup.open()
                except AttributeError:
                    # stops from crashing if user hits cancel
                    pass


class AddLabPopup(Popup):
    """class for popup on Add screen to switch to another screen"""

    def goToMenu(self):
        """method to switch to menu screen"""
        sm.current = 'menu'

    def goToMach(self):
        """method to switch to machine screen"""
        sm.current = 'machine'


class ChangeLinkPopup(Popup):
    """lets user select which jlab to move a machine to"""
    m = 0
    b = 0

    def getM(self, p):
        self.m = p

    def edit_link(self):
        global privileges_strings
        try:
            m_c = int(self.m[0])
            jl = int(report_jlabs[0])
            cur.execute('select {} from jlabs where jlab_number = {}'.format(privileges_strings["jlabs"], jl))
            lab = cur.fetchone()
            if lab[-1] == 'inactive':
                self.popup = InactiveLink()
                self.popup.open()
            else:
                cur.execute("DELETE FROM hardware WHERE machine_code = {}".format(m_c))
                cur.execute(cur.execute("INSERT INTO hardware VALUES {}".format((jl, m_c))))
                conn.commit()
                self.b.children[1].text = str(jl)
                self.dismiss()
        except IndexError:
            self.popup = SelectJLabPopup()
            self.popup.open()

    def getBox(self, box):
        self.b = box

    def unlink(self):
        m_c = int(self.m[0])
        cur.execute("DELETE FROM hardware WHERE machine_code = {}".format(m_c))
        conn.commit()
        self.b.children[1].text = "None"


class StatusPopup(Popup):
    """make sure user really wants to change the status of a machine or jlab """
    code = 0
    box = None
    type = None

    def getCode(self, c, b, mOrj):
        self.code = c
        self.box = b
        self.type = mOrj

    def changeStatus(self):
        global current_user
        global privileges_strings
        # MYSQL stuff
        if self.type == 'm':
            cur.execute(
                "Select {} from machine where machine_code = {}".format(privileges_strings["machine"], self.code))
            mach = cur.fetchone()
            status = mach[-1]
            opposite = 'active'
            if status == 'active':
                opposite = 'inactive'
            self.box.children[1].text = opposite
            cur.execute("update machine set m_status = \"{}\" where machine_code = {}".format(opposite, self.code))
            conn.commit()

        elif self.type == 'j':
            cur.execute("Select {} from jlabs where jlab_number = {}".format(privileges_strings["jlabs"], self.code))
            jlab = cur.fetchone()
            status = jlab[-1]
            opposite = 'active'
            if status == 'active':
                opposite = 'inactive'
            self.box.children[1].text = opposite
            cur.execute("update jlabs set j_status = \"{}\" where jlab_number = {}".format(opposite, self.code))
            conn.commit()
            # TRACK HISTORY  status of jlab self.code changed from status to opposite
            cur.execute("insert into history ( jlab_number, user, changed, prev_data, curr_data) values {}".format(
                (self.code, str(current_user), 'Changed JLab Activity', str(status), opposite)))
            conn.commit()


class InvalidJLabPopup(Popup):
    """
    popup for if a user tries to create a jlab with an already existing code
    """
    over = False

    def overT(self):
        self.over = True


class QuitPopup(Popup):
    """Class to quit screen when 'yes' is selected in the popup
    :param: None
    :return: None
    """
    global cur
    global conn

    def quitScreen(self):
        """ calls exit"""
        global cur
        global conn
        cur.close()
        conn.close()
        exit(1)

# ##################################################   END POPUPS  #####################################################
# ##################################################  BEGIN MISC  ######################################################


class MyTreeView(TreeView):
    """
    This class defines a TreeViewNode with a CheckBox and a Label.
        updateChildren() defines the behavior of checkboxes within the tree and is called in the TreeViewCBNode rule in the load_string (or kv file) on_press.
    """
    hide_root = True
    indent_level = 50

    def populate_treeview(self, parent, node):
        """
        formats tree for GUI treeview-ing
        :param parent: parent of current node
        :param node: child node of parent
        :return:
        """
        tree_node = self.add_node(self.TreeViewCBNode(text=node['node_id'], is_open=True), parent)
        for child_node in node['children']:
            self.populate_treeview(tree_node, child_node)

    def create_tree(self):
        """
        Queries Hardware table in db and formats tree for treeview by creating nested lists/dictionaries.
        Passes final tree to populate_treeview so it is in GUI.
        :return:
        """
        global privileges_strings
        # Empty tree list to populate with nodes (i.e. Dictionaries)
        tree = []
        # Empty list to save node_id names
        node_ids = []
        # Query Hardware table for column names, which will indicate the node_ids
        cur.execute("SELECT {} FROM hardware".format(privileges_strings["hardware"]))
        names = list(map(lambda x: x[0], cur.description))
        for name in names:
            node_ids.append(name)
        # Test nodes against fk list to identify which have children
        fks = get_fks("hardware")
        fk_tables = get_fk_tables("hardware")
        currDict = {}
        currDict['node_id'] = node_ids[0]
        currDict['children'] = []
        for fkey in fks:
            # Deals with the jlab_number from Hardware table
            if node_ids[0] == fkey:
                # Query table for column names, which will indicate the node_ids
                cur.execute("SELECT {} FROM {}".format(privileges_strings[str(fk_tables[fks.index(fkey)])],
                                                       fk_tables[fks.index(fkey)]))
                names = list(map(lambda x: x[0], cur.description))
                # Slice out id
                names = names[1:len(names)]
                for name in names:
                    if name in dbDict:
                        # Use nicely formatted version of field in dbDict{}
                        nDict = {'node_id': dbDict[name], 'children': []}
                    else:
                        nDict = {'node_id': name, 'children': []}
                    currDict['children'].append(nDict)
                    # Company & Owner
                    sub_fks = get_fks("jlabs")
                    sub_fk_tables = get_fk_tables("jlabs")
                    for subkey in sub_fks:
                        if name == subkey:
                            cur.execute(
                                "SELECT {} FROM {}".format(privileges_strings[sub_fk_tables[sub_fks.index(subkey)]],
                                                           sub_fk_tables[sub_fks.index(subkey)]))
                            sub_names = list(map(lambda x: x[0], cur.description))
                            # Slice out id
                            sub_names = sub_names[1:len(sub_names)]
                            for sub_name in sub_names:
                                if sub_name in dbDict:
                                    # Use nicely formatted version of field in dbDict{}
                                    nDict['children'].append({'node_id': dbDict[sub_name], 'children': []})
                                else:
                                    nDict['children'].append({'node_id': sub_name, 'children': []})
            # Deals with the machine_code from Hardware table
            if node_ids[1] == fkey:
                mDict = {'node_id': dbDict[node_ids[1]], 'children': []}
                currDict['children'].append(mDict)
                # Query table for column names, which will indicate the node_ids
                cur.execute("SELECT {} FROM {}".format(privileges_strings[fk_tables[fks.index(fkey)]],
                                                       fk_tables[fks.index(fkey)]))
                m_names = list(map(lambda x: x[0], cur.description))
                # Slice out id
                m_names = m_names[1:len(m_names)]
                for m_name in m_names:
                    if m_name in dbDict:
                        # Use nicely formatted version of field in dbDict{}
                        mDict['children'].append({'node_id': dbDict[m_name], 'children': []})
                    else:
                        mDict['children'].append({'node_id': m_name, 'children': []})
        tree.append(currDict)
        for branch in tree:
            if branch['node_id'] == 'jlab_number':
                for sub_branch in branch['children']:
                    self.populate_treeview(None, sub_branch)
            else:
                self.populate_treeview(None, branch)

    class TreeViewCBNode(CheckBox, Label, TreeViewNode):
        """
        This class defines a TreeViewNode with a CheckBox and a Label.
        updateChildren() defines the behavior of checkboxes within the tree and is called in the TreeViewCBNode rule in the load_string (or kv file) on_press.
        """

        def updateChildren(self):
            # Sets child nodes to active when checking parent
            if not self.is_leaf:
                if not self.is_open:
                    self.parent.toggle_node(self)
                for node in self.parent.iterate_open_nodes(self):
                    node.active = self.active

            # Sets parent node to checked when checking a child, or unchecked when unchecking all children
            if self.parent_node:
                flag = 0
                if not self.active:
                    for node in self.parent.iterate_open_nodes(self.parent_node):
                        if node.active:
                            flag += 1
                if flag < 2:
                    self.parent_node.active = self.active

        def selected_cbs(self, instance):
            # if there is something in report names...
            if len(report_names) > 0:
                # if selected cb is already in report_names, it is actually being de-selected
                if instance.text in report_names:
                    report_names.remove(instance.text)
                else:
                    # otherwise, it's being added
                    report_names.append(instance.text)
            else:
                # otherwise it's being added for the first time
                report_names.append(instance.text)


class WelcomeBoxLayout(BoxLayout):
    # Custom color BoxLayout
    pass


class SelectableGrid(CompoundSelectionBehavior, GridLayout):
    n_list = []

    def make_buttons(self, grid):
        global privileges_strings
        b_list = populate_jlab_buttons()
        grid.clear_widgets()
        for title in b_list:
            cur.execute('select {} from jlabs where jlab_number = {}'.format(privileges_strings["jlabs"], title))
            lab = cur.fetchone()
            if lab[-1] == 'inactive':
                btn = Button(text=str(title),
                             id=("id" + str(title)), size=(400, 50), color=(1, 0, 0, 1))
            else:
                btn = Button(text=str(title),
                             id=("id" + str(title)), size=(400, 50))
            grid.add_widget(btn)
        self.g = grid
        return grid

    def update_buttons(self, grid):
        global privileges_strings
        b_list = populate_jlab_buttons()
        grid.clear_widgets()
        for title in b_list:
            cur.execute('select {} from jlabs where jlab_number = {}'.format(privileges_strings["jlabs"], title))
            lab = cur.fetchone()
            if lab[-1] == 'inactive':
                btn = Button(text=str(title),
                             id=("id" + str(title)), size=(400, 50), color=(1, 0, 0, 1))
            else:
                btn = Button(text=str(title),
                             id=("id" + str(title)), size=(400, 50))
            grid.add_widget(btn)
        self.g = grid
        self.size = (400, self.getNumJLabs() * 35)
        return grid

    def add_widget(self, widget):
        """ Override the adding of widgets so we can bind and catch their
        *on_touch_down* events. """
        widget.bind(on_touch_down=self.button_touch_down,
                    on_touch_up=self.button_touch_up)
        self.n_list.append(widget)
        return super(SelectableGrid, self).add_widget(widget)

    def button_touch_down(self, button, touch):
        """ Use collision detection to select buttons when the touch occurs
        within their area. """
        if button.collide_point(*touch.pos):
            self.select_with_touch(button, touch)

    def button_touch_up(self, button, touch):
        """ Use collision detection to de-select buttons when the touch
        occurs outside their area and *touch_multiselect* is not True. """
        if not (button.collide_point(*touch.pos) or
                self.touch_multiselect):
            self.deselect_node(button)

    def select_node(self, node):
        node.background_color = (0, 182, 229, .667)
        x = node.parent.parent.parent.parent.parent.parent
        try:
            x.create_history_table(node.text, x.ids.hBox, x.ids.hLb, x.ids.j_grid, '')
        except:
            try:
                x.refresh_table(node.text, x.ids.oBox1, x.ids.jbox, x.ids.mLb, x.ids.mbox1, x.ids.grid)
            except AttributeError:
                pass
        return super(SelectableGrid, self).select_node(node)

    def deselect_node(self, node):
        node.background_color = (1, 1, 1, 1)
        super(SelectableGrid, self).deselect_node(node)

    def on_selected_nodes(self, grid, nodes):
        del report_jlabs[:]
        for node in nodes:
            report_jlabs.append(node.text)
        return report_jlabs

    def select_all_nodes(self, grid):
        for node in grid.children:
            node.background_color = (0, 182, 229, .667)
            super(SelectableGrid, self).select_node(node)

    def deselect_all_nodes(self, grid):
        for node in grid.children:
            node.background_color = (1, 1, 1, 1)
            super(SelectableGrid, self).deselect_node(node)

    def getNumJLabs(self):
        """gets number of jlabs
        :return: length of list, int"""
        cur.execute("SELECT * FROM jlabs")
        rows = cur.fetchall()
        return len(rows)


class OwnerSelectableGrid(CompoundSelectionBehavior, GridLayout):
    n_list = []

    def make_owner_buttons(self, grid):
        global privileges_strings

        grid.clear_widgets()
        del report_owners[:]

        cur.execute("SELECT {} FROM owner".format(privileges_strings["owner"]))
        rows = cur.fetchall()
        for row in rows:
            currRow = []
            for i in range(1, len(row)):
                currRow.append(str(row[i]))
            report_owners.append(currRow)

        for row in report_owners:
            btn = Button(text=row[0],
                         id=("id" + row[0]))
            btn.size_hint = (1, None)
            btn.height = 50
            grid.add_widget(btn)

        # Resize according to number of buttons
        self.size = (400, 50 * (len(rows)))

        return grid

    def add_widget(self, widget):
        """ Override the adding of widgets so we can bind and catch their
        *on_touch_down* events. """
        widget.bind(on_touch_down=self.button_touch_down,
                    on_touch_up=self.button_touch_up)
        self.n_list.append(widget)
        return super(OwnerSelectableGrid, self).add_widget(widget)

    def button_touch_down(self, button, touch):
        """ Use collision detection to select buttons when the touch occurs
        within their area. """
        del report_owner_info[:]
        if button.collide_point(*touch.pos):
            self.select_with_touch(button, touch)

    def button_touch_up(self, button, touch):
        """ Use collision detection to de-select buttons when the touch
        occurs outside their area and *touch_multiselect* is not True. """
        if not (button.collide_point(*touch.pos) or
                self.touch_multiselect):
            self.deselect_node(button)

    def select_node(self, node):
        node.background_color = (0, 182, 229, .667)
        return super(OwnerSelectableGrid, self).select_node(node)

    def deselect_node(self, node):
        node.background_color = (1, 1, 1, 1)
        super(OwnerSelectableGrid, self).deselect_node(node)

    def on_selected_nodes(self, grid, nodes):
        for node in nodes:
            report_owner_info.append(node.text)
        return report_owner_info


class UserSelectableGrid(CompoundSelectionBehavior, GridLayout):

    def make_user_buttons(self, grid):
        grid.clear_widgets()

        # Get users with access to 'test' database
        cur.execute("SELECT user from users")
        rows = cur.fetchall()

        for row in rows:
            btn = Button(text=str(row[0]), id=("id" + str(row[0])), size_hint=(1, None), height=50)
            grid.add_widget(btn)

        # Resize according to number of buttons
        self.size = (400, 50 * (len(rows)))

        return grid

    def add_widget(self, widget):
        """ Override the adding of widgets so we can bind and catch their
        *on_touch_down* events. """
        widget.bind(on_touch_down=self.button_touch_down,
                    on_touch_up=self.button_touch_up)
        return super(UserSelectableGrid, self).add_widget(widget)

    def button_touch_down(self, button, touch):
        """ Use collision detection to select buttons when the touch occurs
        within their area. """
        del report_owner_info[:]
        if button.collide_point(*touch.pos):
            self.select_with_touch(button, touch)

    def button_touch_up(self, button, touch):
        """ Use collision detection to de-select buttons when the touch
        occurs outside their area and *touch_multiselect* is not True. """
        if not (button.collide_point(*touch.pos) or
                self.touch_multiselect):
            self.deselect_node(button)

    def select_node(self, node):
        node.background_color = (0, 182, 229, .667)
        return super(UserSelectableGrid, self).select_node(node)

    def deselect_node(self, node):
        node.background_color = (1, 1, 1, 1)
        super(UserSelectableGrid, self).deselect_node(node)

    def deselect_all_nodes(self, grid):

        for node in grid.children:
            node.background_color = (1, 1, 1, 1)
            super(UserSelectableGrid, self).deselect_node(node)

        x = grid.parent.parent.parent.parent.parent.parent
        try:
            try:
                x.create_history_table(report_jlabs[0], x.ids.hBox, x.ids.hLb, x.ids.j_grid, "")
            except IndexError:
                x.create_history_table(-1, x.ids.hBox, x.ids.hLb, x.ids.j_grid, "")
        except AttributeError:
            pass

    def on_selected_nodes(self, grid, nodes):
        x = ""
        for node in nodes:
            x = node.parent.parent.parent.parent.parent.parent
        try:
            try:
                x.create_history_table(report_jlabs[0], x.ids.hBox, x.ids.hLb, x.ids.j_grid, node.text)
            except IndexError:
                x.create_history_table(-1, x.ids.hBox, x.ids.hLb, x.ids.j_grid, node.text)
        except AttributeError:
            pass

        return

    def get_num_users(self):

        # Get users with access to 'test' database
        cur.execute("SELECT User FROM mysql.db WHERE Db = 'test'")
        rows = list(cur.fetchall())

        return len(rows)


class Tooltip(Label):
    pass


class MyToggleButton(ToggleButton):

    def __init__(self, **kwargs):
        super(ToggleButton, self).__init__(**kwargs)
        self.allow_no_selection = False


class MyTextInput(TextInput):
    pass


# #################################################### END MISC  #######################################################
# ################################################   BEGIN SCREENS   ###################################################

# Declare screens
class LoginScreen(Screen):
    text = ''

    def login(self, user_in, pass_in):
        # Set up connection and cursor with user input login info
        global conn
        global cur
        global privileges_strings
        global current_user

        try:
            conn = mysql.connector.connect(user='root', password='', host='127.0.0.1', database='jlabdb')
            cur = conn.cursor(buffered=True)
            try:
                cur.execute("SELECT password from users where user = \"{}\"".format(user_in))
                pw = str(cur.fetchone()[0])

                # If password exists for username, check given pass_in against password
                if len(pw) > 0:
                    while pass_in != pw:
                        raise TypeError('Incorrect Login Info')
                    else:
                        current_user = user_in
                        set_user_privs(user_in)

                        # Dictionary holding nicely formatted names for database fields (used in def create_tree() and similar methods throughout the program)
                        # Moved to here because it needs to refer to the DB which can only happen after a successful login (determined in create_connection)
                        # Function for the method to check for additional columns and add them in the correct order to the dictionary

                        def newColumn(table_name, last_col):
                            """
                            :param: table_name = table to check
                            :param: last_col = most recent column in dbDict
                            """
                            column_list = get_columns(table_name)
                            if len(column_list) > column_list.index(last_col):
                                for colNo in range(column_list.index(last_col) + 1, len(column_list)):
                                    dbDict[str(column_list[colNo])] = str(column_list[colNo])

                        global dbDict

                        dbDict = collections.OrderedDict()
                        dbDict['jlab_number'] = 'JLab #'
                        dbDict['location'] = 'Location'
                        dbDict['igss_version'] = 'IGSS Version'
                        dbDict['ccts_version'] = 'CCTS Version'
                        dbDict['data_source'] = 'Data Source'

                        dbDict['owner_code'] = 'Owner Info:'
                        dbDict['owner_name'] = 'Owner\'s Name'
                        dbDict['owner_email'] = 'Owner\'s Email'
                        dbDict['owner_phone'] = 'Owner\'s Phone #'
                        # ADDITIONAL COLUMN IN OWNER TABLE
                        newColumn('owner', 'owner_phone')

                        dbDict['company'] = 'Company'
                        dbDict['jlab_comments'] = 'JLab Comments'
                        dbDict['j_status'] = 'JLab Status'
                        # ADDITIONAL COLUMN IN JLAB TABLE
                        newColumn('jlabs', 'j_status')

                        dbDict['machine_code'] = 'Machine(s) Info:'
                        dbDict['machine_name'] = 'Machine Name'
                        dbDict['machine_company'] = 'Machine Company'
                        dbDict['m_owner_code'] = 'Machine Owner'

                        dbDict['serial_number'] = 'Machine Serial #'
                        dbDict['ip_address'] = 'IP Address'
                        dbDict['model_number'] = 'Model #'
                        dbDict['operating_system'] = 'Operating System'
                        dbDict['esn'] = 'ESN'
                        dbDict['specs'] = 'Specifications'
                        dbDict['machine_comments'] = 'Machine Comments'
                        dbDict['m_status'] = 'Machine Status'
                        # ADDITIONAL COLUMN IN MACHINE TABLE
                        newColumn('machine', 'm_status')

                        # Add other content to screen manager after successful login
                        sm.remove_widget(LoginScreen(name='login'))
                        sm.add_widget(ReportScreen(name='report'))
                        sm.add_widget(MenuScreen(name='menu'))
                        sm.add_widget(AddScreen(name='add'))
                        sm.add_widget(MachineScreen(name='machine'))
                        sm.add_widget(LookupScreen(name='lookup'))
                        sm.add_widget(AdvancedLookupScreen(name='advanced_lookup'))
                        sm.add_widget(MachineLookupScreen(name='mach_lookup'))
                        sm.add_widget(LinkScreen(name='link'))
                        sm.add_widget(HistoryScreen(name='history'))
                        sm.current = 'menu'
            except TypeError:
                self.text = 'Failed login attempt! Please try again.'
        except mysql.connector.errors.ProgrammingError as e:
            print(e)
            self.text = 'Base login failure. Please contact the database administrator.'

    def popQuitProgram(self):
        self.popup = QuitPopup()
        self.popup.open()

    def getText(self):
        return self.text


class MenuScreen(Screen):
    global current_user

    def welcome_msg(self, wel, wel_msg):
        # Make welcome message utilizing username
        wel_msg.color = (1, 1, 1, .9)
        wel_msg.italic = True
        wel_msg.font_size = 20
        wel_msg.text = "Welcome, " + current_user + "."
        wel_width = len(wel_msg.text) * 15
        wel_height = wel_msg.height

        wel.width = wel_width
        wel.height = wel_height

    def popQuitProgram(self):
        self.popup = QuitPopup()
        self.popup.open()


class ReportScreen(Screen):
    """class for the Report Screen """

    popup = ObjectProperty(None)
    text = ''

    def __init__(self, **kwargs):
        """init method"""
        super(ReportScreen, self).__init__(**kwargs)

    def popClearSelections(self, grid, TV):
        """"method to create popup used to clear all selections on this screen,
        creates popup and methods called from that popup screen"""
        self.popup = ClearSelection()
        self.popup.open()

        # method which checks response to popup(activates on closing)
        def clears(self):
            if self.yes:
                for node in TV.iterate_all_nodes():
                    node.active = False
                grid.deselect_all_nodes(grid)
                grid.parent.parent.children[4].children[0].children[1].text = ''

        self.popup.bind(on_dismiss=clears)

    def select_all_grid(self, grid):
        """ Method to select all JLabs
        :param: grid: 'list' with all JLabs
        """
        grid.select_all_nodes(grid)

    def select_all_TV(self, TV):
        """ Method to select all JLab Info
        :param: TV: treeview with all JLab Info options
        """
        for node in TV.iterate_all_nodes():
            node.active = True

    def printReport(self, unattached_btn):
        """
        Creates a report in csv file format
        Currently requires user to save file with extension .csv, otherwise does nothing
        Does not generate a report if no jlab is selected or if no field is selected
        TO DO: Add popups to tell user if file was not created and why,
        Find a way to make default filename jlabs_inv_report.csv
        """

        # Sort report_names based on the order of values in dbDict
        sorted_report_names = sorted(report_names, key=lambda x: dbDict.values().index(x))

        report_fields = []
        # Sort selected JLabs by integer within string
        report_jlabs.sort(key=int)

        # "Translate" fields in report_names back to database attribute names
        dbDict_vals = list(dbDict.values())
        dbDict_keys = list(dbDict.keys())

        for name in sorted_report_names:
            if name in dbDict_vals:
                index = dbDict_vals.index(name)
                report_fields.append(dbDict_keys[index])

        # ZEB
        if (len(report_jlabs) > 0 or unattached_btn.state == 'down') and len(report_fields) > 0:
            popup = SaveDialog(self)
            popup.rprt_fields = report_fields
            popup.rprt_jlabs = report_jlabs
            popup.open()
        else:
            # Will later be a popup
            print("You must select at least one JLab and at least one field. No file created.")
            popup = NoSelectionErrorPopup()
            popup.open()

    def ReadInput(self):
        """method allows users to type jlab number and lookup instead of scrolling through jlabs """
        SelectedJlab = (self.children[1].children[1].children[4].children[0].children[1].text)
        grid = self.children[1].children[1].children[2].children[0]
        abc = 0
        # grid.deselect_all_nodes(grid)
        for a in self.children[1].children[1].children[2].children[0].children:
            if str(a.text) == str(SelectedJlab):
                grid.select_node(a)
                abc = 1
        if abc == 0:
            if SelectedJlab != '':
                self.popup = LookupErrorPopup()
                self.popup.open()
        self.children[1].children[1].children[4].children[0].children[1].text = ''


class LookupScreen(Screen):
    """class for the lookup screen"""

    # create a tooltip for this screen
    tooltip_look = Tooltip()
    # list of all text inputs that need tooltips
    tis_look = []

    # TOOLTIP METHODS
    def __init__(self, **kwargs):
        """
        init creates screen to be ready to track mouse movements
        :param kwargs:
        """
        Window.bind(mouse_pos=self.on_mouse_pos)
        super(Screen, self).__init__(**kwargs)

    def on_mouse_pos(self, *args):
        """
        tracks mouse position and shows tooltip when mouse is over the comment tab
        :param args:
        :return:
        """
        if not self.get_root_window():
            return
        pos = args[1]
        self.tooltip_look.pos = pos
        x = self.tooltip_look.pos[0] - self.tooltip_look.size[0]
        self.tooltip_look.pos = (x, self.tooltip_look.pos[1])
        Clock.unschedule(self.display_tooltip)  # cancel scheduled event since I moved the cursor
        self.close_tooltip()  # close if it's opened
        for i in self.tis_look:
            if Label(pos=i.to_window(*i.pos), size=i.size).collide_point(*self.to_widget(*pos)):
                self.tooltip_look.text = i.text
                Clock.schedule_once(self.display_tooltip, 1)

    def close_tooltip(self, *args):
        Window.remove_widget(self.tooltip_look)

    def display_tooltip(self, *args):
        Window.add_widget(self.tooltip_look)

    # END TOOLTIP METHODS

    popup = ObjectProperty(None)
    machine_labels = []
    mach_db = []
    prev_sel_jlab = -1

    # List (of lists for mach_db) to hold data from database
    jlab_db = []
    own_db = []
    mach_db = []
    m_code = None

    num = 0

    def createTable(self, jbox, lb):
        """method to create a table holding info about the currently selected jlab
        This defaults to no jlab being selected, and thus the JLabs info is N/A
        :param: box: row of textinputs
        :param: lb: labels of jLab info"""
        global test_schema
        b = jbox
        b.size_hint = 1, 1

        jLabels = copy.deepcopy(test_schema["jlabs"])
        # Remove jlab_number field
        del jLabels[0]

        # Remove fields that are just foreign keys
        for lab in jLabels:
            if "_code" in lab:
                jLabels.remove(lab)

        # Unattached machine won't have JLab info, so 'N/A'
        for lab in jLabels:
            lb.add_widget(Label(text="", halign='center'))

        b.add_widget(TextInput(text="", readonly=True, disabled=True, background_disabled_normal='', background_color=(0, 0, 0, 0)))

    def createOtable(self, oBox, oLb):
        """
        :param oBox: row of textinputs for Onwer info
        :param oLb: labels for owner info
        :return:
        """
        b = oBox
        b.size_hint = 1, 1

        oLabels = get_columns("owner")

        # Remove owner_code field
        del oLabels[0]

        # Unattached machine won't have JLab info, so 'N/A'
        for lab in oLabels:
            oLb.add_widget(Label(text="", halign='center'))

        b.add_widget(TextInput(text="", readonly=True, disabled=True, background_disabled_normal='', background_color=(0, 0, 0, 0)))

    def getNum(self):
        """gets the length of machine_info aka how many machines are in the jlab
        :return: length of list, int"""
        global privileges_strings
        # Now populate table with machines not listed on Hardware table (i.e. unattached machines)
        cur.execute("SELECT {} FROM machine WHERE machine_code NOT IN(SELECT machine_code FROM hardware)".format(
            privileges_strings["machine"]))
        rows = cur.fetchall()
        return len(rows)

    def get_selected_jlab(self):
        """calls the deselect all method from the SelectableGrid class"""
        # Check if jlab was selected
        if len(report_jlabs) > 0:
            sel_jlab = report_jlabs[0]
        else:
            sel_jlab = -1
        return sel_jlab

    def refresh_table(self, jlab_num, oBox1, jbox, mLb, mbox1, grid):
        """
        refreshes table when changes are made to the database
        :param oBox1: owner row
        :param jbox: jlab row
        :param mbox1:  machine row1
        :param mbox2:  machine other rows
        :return: None"""
        global privileges_strings
        global test_schema
        global restrictions_list

        self.num = jlab_num
        # Only refresh screen if NEW JLab is selected
        if jlab_num != self.prev_sel_jlab:
            # Update previously selected JLab
            self.prev_sel_jlab = jlab_num

        # Clear mach_db and all recalled data
        self.mach_db = []
        self.jlab_db = []
        self.own_db = []

        # Remove all widgets
        jbox.clear_widgets()
        mbox1.clear_widgets()
        oBox1.clear_widgets()

        obox = oBox1
        b = jbox

        # display unattached machines
        if jlab_num < 0:
            mLb.clear_widgets()

            # Deselect nodes so currently selected JLab defaults back to -1
            grid.deselect_all_nodes(grid)

            # REPLACE JLAB INFO
            b.add_widget(TextInput(text='', write_tab=False, background_color=(1, 1, 1, 0)))

            # REPLACE OWNER INFO
            obox.add_widget(TextInput(text='', write_tab=False, background_color=(1, 1, 1, 0)))

            # REPLACE MACHINE INFO

            # GET RID OF OTHER WIDGETS SO SCREEN ONLY SHOWS UNATTACHED MACHINES
            rightSideList = oBox1.parent.children

            # was 'JLabs'
            rightSideList[8].text = ''
            # used to be JLab table labels
            for label in rightSideList[7].children:
                label.text = ''

            # was 'Owner'
            rightSideList[5].clear_widgets()
            rightSideList[5].add_widget(Label(text='Unattached Machines', font_size=50, size_hint=(.1, 1)))
            rightSideList[5].valign = 'middle'
            # used to be Owner table labels
            for label in rightSideList[4].children:
                label.text = ''

            # Restore Machine label, if necessary
            rightSideList[2].text = 'Machine(s)'
            # Restore Machine header labels if necessary
            machine_labels1 = copy.deepcopy(test_schema["machine"])
            # Remove machine_code field
            del machine_labels1[0]
            del machine_labels1[2]

            for lab in machine_labels1:
                if lab in dbDict:
                    mLb.add_widget(Label(text=dbDict[lab], halign='center'))
                else:
                    mLb.add_widget(Label(text=lab, halign='center'))

            # Populate table with machines not listed on Hardware table (i.e. unattached machines)
            cur.execute("SELECT {} FROM machine WHERE machine_code NOT IN(SELECT machine_code FROM hardware)".format(
                privileges_strings["machine"]))
            rows = cur.fetchall()

            # Convert to list of strings
            for row in rows:
                row = list(row)
                self.m_code = row[0]
                for i in range(len(row)):
                    row[i] = str(row[i])

                row, missing_indices = null_user_restrictions("machine", row)

                del row[0]
                del row[2]
                for i in range(len(missing_indices)):
                    # have to shift indices of restricted column since deleted machine_code and m_owner_code
                    missing_indices[i] = missing_indices[i] - 2
                self.mach_db.append(row)

            # reset height
            mbox1.size = (400, len(self.mach_db) * 35)

            # Have to recreate mbox2 in mbox1
            b3 = BoxLayout(orientation='horizontal')
            # Add new widgets
            mbox1.add_widget(b3)
            for i in range(len(self.mach_db)):
                currMach = []
                for j in range(len(self.mach_db[0])):
                    cur.execute(
                        "select machine_code from machine where machine_name = '{}' ".format(self.mach_db[i][0]))
                    m_code = cur.fetchone()[0]
                    if j in missing_indices:
                        b3.add_widget(TextInput(text=self.mach_db[i][j], readonly=True, disabled=True))
                    elif machine_labels1[j] == 'machine_comments':
                        # these are the boxes that need tooltips
                        if self.mach_db[i][j] == 'None':
                            r_ti = MyTextInput(text='', write_tab=False, multiline=False)
                        else:
                            r_ti = MyTextInput(text=self.mach_db[i][j], write_tab=False)
                        self.tis_look.append(r_ti)
                        b3.add_widget(r_ti)
                    elif machine_labels1[j] == 'm_status':
                        statusBox1 = BoxLayout(padding=5, spacing=5)
                        status = Label(text=self.mach_db[i][j])
                        statBTN = Button(text='change')
                        statBTN.bind(on_release=partial(self.changeStat, 'm', self.mach_db[i][j], m_code, statusBox1))
                        statusBox1.add_widget(status)
                        statusBox1.add_widget(statBTN)
                        b3.add_widget(statusBox1)
                    elif machine_labels1[j] == 'machine_company':
                        compBox = BoxLayout()
                        if self.mach_db[i][j] == 'None':
                            comp = TextInput(text='',write_tab=False, size_hint=(.8, 1))
                        else:
                            comp = TextInput(text=self.mach_db[i][j],write_tab=False, size_hint=(.8, 1))
                        compBTN = Button(text='+', size_hint=(.2, 1))
                        compBTN.bind(on_release=partial(self.compOwner, self.mach_db[i][2], m_code, compBox))
                        compBox.add_widget(comp)
                        compBox.add_widget(compBTN)
                        b3.add_widget(compBox)
                    elif machine_labels1[j] == 'm_owner_code':
                        pass
                    elif self.mach_db[i][j] == 'None':
                        b3.add_widget(TextInput(text='', write_tab=False, multiline=False))
                    else:
                        b3.add_widget(TextInput(text=self.mach_db[i][j], write_tab=False, multiline=False))
                    currMach.append(self.mach_db[i][j])
                b3 = BoxLayout(orientation='horizontal')
                if i < len(self.mach_db) - 1:
                    mbox1.add_widget(b3)
        # create tables for jlabs
        else:
            cur.execute("SELECT {} FROM jlabs WHERE jlab_number = {}".format(privileges_strings["jlabs"], jlab_num))
            jrow = cur.fetchone()

            # Convert to list of strings
            temp = list(jrow)
            j_code = temp[0]
            for item in temp:
                self.jlab_db.append(str(item))
            jrow, missing_j_indices = null_user_restrictions("jlabs", self.jlab_db)
            del jrow[0]
            del jrow[4]

            # bring back labels
            rightSideList = oBox1.parent.children
            rightSideList[8].text = 'JLab'
            rightSideList[5].clear_widgets()
            rightSideList[5].add_widget(Label(size_hint=(.55, 1)))
            rightSideList[5].add_widget(Label(text='Owner', font_size=20, size_hint=(.1, 1)))
            self.popup = OwnerPopup()
            x = self.popup
            btn = Button(text='Options', size_hint=(.1, 1))
            btn.bind(on_press=self.ownerOptions)
            rightSideList[5].add_widget(btn)
            rightSideList[5].add_widget(Label(size_hint=(.45, 1)))
            # repopulate jLabels
            jLabels = copy.deepcopy(test_schema["jlabs"])
            # Remove jlab_number field
            del jLabels[0]
            # Remove fields that are just foreign keys
            shift = 0
            for lab in jLabels:
                if "_code" in lab:
                    jLabels.remove(lab)
                    shift += 1
            for i in range(len(missing_j_indices)):
                # have to shift indices of restricted column to account for jlabel deletions
                missing_j_indices[i] -= 1
            count = len(jLabels) - 1
            for lab in jLabels:
                rightSideList[7].children[count].text = dbDict[lab]
                count -= 1

            # repopulate owner labels
            oLabels = get_columns("owner")

            # Remove owner_code field
            del oLabels[0]
            oLabels.reverse()

            count = 0
            for lab in oLabels:
                if lab in dbDict:
                    rightSideList[4].children[count].text = dbDict[lab]
                else:
                    # in case another Owner field is added in the db down the line
                    rightSideList[4].children[count].text = lab
                count += 1

            for i in range(len(jLabels)):
                if i in missing_j_indices:
                    b.add_widget(TextInput(text=jrow[i], readonly=True, disabled=True))
                elif jLabels[i] == 'jlab_comments':
                    if jrow[i] == 'None':
                        ti = MyTextInput(text='', write_tab=False)
                    else:
                        ti = MyTextInput(text=jrow[i], write_tab=False)
                    self.tis_look.append(ti)
                    b.add_widget(ti)
                elif jLabels[i] == 'j_status':
                    statusBox2 = BoxLayout(padding=5, spacing=5)
                    status = Label(text=jrow[i])
                    statBTN = Button(text='change')
                    statBTN.bind(on_release=partial(self.changeStat, 'j', jrow[i], j_code, statusBox2))
                    statusBox2.add_widget(status)
                    statusBox2.add_widget(statBTN)
                    b.add_widget(statusBox2)
                else:
                    if jrow[i] == 'None':
                        b.add_widget(TextInput(text='', write_tab=False))
                    else:
                        b.add_widget(TextInput(text=jrow[i], write_tab=False))

                # REPLACE OWNER INFO
                cur.execute("SELECT {} FROM owner WHERE owner_code IN "
                            "(SELECT owner_code FROM jlabs WHERE jlab_number = {})".format(privileges_strings["owner"],
                                                                                           jlab_num))
                orow = cur.fetchone()

            if orow is None:
                # No owner linked to JLab
                o_len = len(get_columns("owner")) - 1
                for i in range(o_len):
                    obox.add_widget(TextInput(text='', readonly=True, disabled=True, disabled_foreground_color=(0, 0, 0, 1)))
            else:
                # Convert to list of strings
                temp = list(orow)
                del temp[0]
                for item in temp:
                    self.own_db.append(str(item))

                for i in range(0, len(self.own_db)):
                    if self.own_db[i] == 'None':
                        obox.add_widget(TextInput(text='', readonly=True, disabled=True, disabled_foreground_color=(0, 0, 0, 1)))
                    else:
                        obox.add_widget(TextInput(text=self.own_db[i], readonly=True, disabled=True,
                                                  disabled_foreground_color=(0, 0, 0, 1)))
            # REPLACE MACHINE INFO
            # Populate table with machines listed on Hardware table and linked to jlab_num
            cur.execute("SELECT {} FROM machine WHERE machine_code IN"
                        "(SELECT machine_code FROM hardware WHERE jlab_number = {})".format(
                privileges_strings["machine"], jlab_num))
            rows = cur.fetchall()

            # Have to recreate mbox2 in mbox1
            b3 = BoxLayout(orientation='horizontal')
            # Add new widgets
            mbox1.add_widget(b3)

            if len(rows) == 0:
                # If there are no machines attached to the selected JLab
                # Used to be Machine label
                rightSideList[2].text = ''

                # used to be Machine table labels
                for label in rightSideList[1].children:
                    label.text = ''

                # reset height: have to hard code height when zero rows returned
                mbox1.size = (400, 70)

                b3.add_widget(Label(text="No Machine(s) to Display", font_size=30))
                b3 = BoxLayout(orientation='horizontal')
                mbox1.add_widget(b3)
            else:
                # Restore Machine label, if necessary
                rightSideList[2].text = 'Machine(s)'

                # Restore Machine header labels if necessary
                machine_labels2 = copy.deepcopy(test_schema["machine"])
                del machine_labels2[0]
                i = 0
                for label in rightSideList[1].children:
                    label.text = dbDict[machine_labels2[len(machine_labels2) - 1 - i]]
                    i += 1
                # Convert to list of strings
                for row in rows:
                    row = list(row)
                    self.m_code = row[0]
                    for i in range(len(row)):
                        row[i] = str(row[i])
                    row, missing_indices = null_user_restrictions("machine", row)
                    del row[0]
                    for i in range(len(missing_indices)):
                        # have to shift indices of restricted column since deleted machine_code
                        missing_indices[i] = missing_indices[i] - 1
                    self.mach_db.append(row)
                # reset height
                mbox1.size = (400, len(self.mach_db) * 35)
                for i in range(len(self.mach_db)):
                    currMach = []
                    for j in range(len(self.mach_db[0])):
                        cur.execute(
                            "select machine_code from machine where machine_name = '{}' ".format(self.mach_db[i][0]))
                        m_code = cur.fetchone()[0]
                        if j in missing_indices:
                            b3.add_widget(TextInput(text=self.mach_db[i][j], readonly=True, disabled=True))
                        elif machine_labels2[j] == 'machine_comments':
                            # these are the boxes that need tooltips
                            ti = MyTextInput(text=self.mach_db[i][j], write_tab=False)
                            self.tis_look.append(ti)
                            b3.add_widget(ti)
                        elif machine_labels2[j] == 'm_status':
                            statusBox3 = BoxLayout(padding=5, spacing=5)
                            status = Label(text=self.mach_db[i][j])
                            statBTN = Button(text='change')
                            statBTN.bind(
                                on_release=partial(self.changeStat, 'm', self.mach_db[i][j], m_code, statusBox3))
                            statusBox3.add_widget(status)
                            statusBox3.add_widget(statBTN)
                            b3.add_widget(statusBox3)
                        elif machine_labels2[j] == 'machine_company':
                            compBox = BoxLayout()
                            if self.mach_db[i][j] == 'None':
                                comp = TextInput(text='', write_tab=False,size_hint=(.8, 1))
                            else:
                                comp = TextInput(text=self.mach_db[i][j],write_tab=False, size_hint=(.8, 1))
                            compBTN = Button(text='+', size_hint=(.2, 1))
                            compBTN.bind(
                                on_release=partial(self.compOwnerJ, self.mach_db[i][2], m_code, compBox))
                            compBox.add_widget(comp)
                            compBox.add_widget(compBTN)
                            b3.add_widget(compBox)
                        elif machine_labels2[j] == 'm_owner_code':
                            pass
                        else:
                            if self.mach_db[i][j] == 'None':
                                b3.add_widget(TextInput(text='', write_tab=False))
                            else:
                                b3.add_widget(TextInput(text=self.mach_db[i][j], write_tab=False))
                    b3 = BoxLayout(orientation='horizontal')
                    if i < len(self.mach_db) - 1:
                        mbox1.add_widget(b3)

    def update_MachineTable(self, mbox1, mLb):
        """
        This method is triggered upon entering the Lookup screen and ensures that the user sees the most up-to-date
        information
        :param mbox1:
        :param oBox1:
        :param mLb:
        :return:
        """
        global test_schema
        global privileges_strings
        global restrictions_list
        self.children[1].children[1].children[0].children[2].children[1].text = ''
        mLb.clear_widgets()
        # Query Machine table to get table header names
        machine_labels0 = copy.deepcopy(test_schema["machine"])
        # Remove machine_code field
        del machine_labels0[0]
        del machine_labels0[2]

        for lab in machine_labels0:
            mLb.add_widget(Label(text=dbDict[lab], halign='center'))

        # Clear mach_db and all recalled data
        self.mach_db = []
        # Remove all widgets
        mbox1.clear_widgets()

        # REPLACE MACHINE INFO
        # Populate table with machines not listed on Hardware table (i.e. unattached machines)
        cur.execute("SELECT {} FROM machine WHERE machine_code NOT IN(SELECT machine_code FROM hardware)".format(
            privileges_strings["machine"]))
        rows = cur.fetchall()

        # Convert to list of strings
        for row in rows:
            # i = rows.index(row)
            # row = list(row)
            # self.m_code = rows[i][0]
            row = list(row)
            self.m_code= row[0]
            del row[0]
            for i in range(len(row)):
                row[i] = str(row[i])
            # Insert "RESTRICTED" as data for restricted columns
            row, missing_indices = null_user_restrictions("machine", row)
            # del row[0]
            for i in range(len(missing_indices)):
                # have to shift indices of restricted column since deleted machine_code
                missing_indices[i] = missing_indices[i] - 1
            self.mach_db.append(row)


        # reset height
        mbox1.size = (400, len(self.mach_db) * 35)

        # Have to recreate mbox2 in mbox1
        b3 = BoxLayout(orientation='horizontal')
        # Add new widgets
        mbox1.add_widget(b3)
        b3.padding = 1.5
        b3.spacing = 2
        for i in range(len(self.mach_db)):
            currMach = []

            for j in range(len(self.mach_db[i])):
                cur.execute("select machine_code from machine where machine_name = \"{}\" ".format(self.mach_db[i][0]))
                m_code = cur.fetchone()[0]
                if j == 2:
                    pass
                elif j == 1:
                    compBox = BoxLayout()
                    if self.mach_db[i][j] == 'None':
                        comp = TextInput(text='',write_tab=False, size_hint=(.8, 1))
                    else:
                        comp = TextInput(text=self.mach_db[i][j], write_tab=False,size_hint=(.8, 1))
                    compBTN = Button(text='+', size_hint=(.2, 1))
                    compBTN.bind(
                        on_release=partial(self.compOwner, self.mach_db[i][2], self.mach_db[i][0], compBox))
                    compBox.add_widget(comp)
                    compBox.add_widget(compBTN)
                    b3.add_widget(compBox)
                elif j == 9:
                    ti = MyTextInput(text=self.mach_db[i][j], write_tab=False)
                    self.tis_look.append(ti)
                    b3.add_widget(ti)
                elif j == 10:
                    statusBox4 = BoxLayout(padding=5, spacing=5)
                    status = Label(text=self.mach_db[i][j])
                    statBTN = Button(text='change')
                    statBTN.bind(on_release=partial(self.changeStat, 'm', self.mach_db[i][j], m_code, statusBox4))
                    statusBox4.add_widget(status)
                    statusBox4.add_widget(statBTN)
                    b3.add_widget(statusBox4)
                else:
                    if self.mach_db[i][j] == 'None':
                        b3.add_widget(TextInput(text='', write_tab=False))
                    else:
                        b3.add_widget(TextInput(text=self.mach_db[i][j], write_tab=False))
                currMach.append(self.mach_db[i][j])
            b3 = BoxLayout(orientation='horizontal')
            b3.padding = 1.5
            b3.spacing = 2
            if i < len(self.mach_db) - 1:
                mbox1.add_widget(b3)

    def rec_j(self, box1):
        """ method to read out all information for the selected jlab"""
        # Prevent use of quotations
        no_quot = True
        # GET JLAB INFO FROM GUI
        for row in box1.children:
            # Exclude active/inactive BoxLayout (0th child)
            for i in range(1, len(row.children)):
                if '"' in row.children[i].text:
                    no_quot = False
        if no_quot:
            # List to hold recalled JLab data
            jlab_rec = []
            j_allowed_indices = []
            rec_jlabels = get_columns("jlabs")
            j_missing_fields, j_missing_indices = null_user_restrictions("jlabs", rec_jlabels)
            del j_missing_fields[0]

            # Shift indices since jlab_number not in recalled boxlayout
            for i in range(len(j_missing_indices)):
                j_missing_indices[i] -= 1

                # GET JLAB INFO FROM GUI
                for row in box1.children:
                    # Exclude active/inactive BoxLayout (0th child)
                    for i in range(len(row.children) - 1, 0, -1):
                        if row.children[i].text == "RESTRICTED":
                            jlab_rec.append(self.jlab_db[-i -1])
                        else:
                            jlab_rec.append(str(row.children[i].text))

                for i in range(len(jlab_rec)):
                    for ind in j_missing_indices:
                        if i != ind:
                            j_allowed_indices.append(i)

                for i in range(len(jlab_rec)):
                    if jlab_rec[i] == '' and self.jlab_db[i] == 'None':
                        jlab_rec[i] = 'None'

                print self.jlab_db[:-1]
                print jlab_rec

                # Check against everything but jlab status
                if self.jlab_db[:-1] == jlab_rec:
                    return False, [], no_quot, j_allowed_indices
                else:
                    return True, jlab_rec, no_quot, j_allowed_indices
            else:
                if len(j_missing_indices) == 0:
                    # GET JLAB INFO FROM GUI
                    for row in box1.children:
                        # Exclude active/inactive BoxLayout (0th child)
                        for i in range(len(row.children) - 1, 0, -1):
                            jlab_rec.append(str(row.children[i].text))
                    for i in range(len(jlab_rec)):
                        j_allowed_indices.append(i)
                    for i in range(len(jlab_rec)):
                        if jlab_rec[i] == '' and self.jlab_db[i] == 'None':
                            jlab_rec[i] = 'None'

                    if self.jlab_db[:-1] == jlab_rec:
                        return True, jlab_rec, no_quot, j_allowed_indices
                    else:
                        return False, [], no_quot, []
                else:

                    return False, [], no_quot, []

    def rec_mach(self, mbox1):
        global test_schema
        # Prevent use of quotations
        no_quot = True
        for row in mbox1.children:
            # Exclude active/inactive BoxLayout (0th child)
            for i in range(1, len(row.children)):
                if isinstance(row.children[i], TextInput):
                    if '"' in row.children[i].text:
                        no_quot = False

        if no_quot:
            # List of lists to hold recalled machine data
            mach_rec = []
            rowi = 0

            rec_mlabels = get_columns("machine")
            m_missing_fields, m_missing_indices = null_user_restrictions("machine", rec_mlabels)
            del m_missing_fields[0]

            # Shift indices since machine_code not in recalled boxlayout
            for i in range(len(m_missing_indices)):
                m_missing_indices[i] -= 1

            rc = 1
            mmm_db = []
            for row in mbox1.children:
                currRow = []
                m_allowed_indices = []
                indx = mbox1.children.index(row)

                # Exclude active/inactive BoxLayout (0th child)
                for i in range(len(row.children) - 1, 0, -1):
                    if isinstance(row.children[i], TextInput):
                        if row.children[i].text != "No Machine(s) to Display":
                            if row.children[i].text != 'RESTRICTED':
                                currRow.append(str(row.children[i].text))
                            else:
                                cur.execute("select * from machine where machine_name = '{}'".format(self.mach_db[-(indx+1)][0]))
                                machine = cur.fetchone()
                                currRow.append(str(machine[-(i+1)]))
                    else:
                        currRow.append(str(row.children[i].children[1].text))
                if rc == 1:
                    # Only get indices of missing fields once
                    for i in range(len(currRow)):
                        if i not in m_missing_indices and i not in m_allowed_indices:
                            m_allowed_indices.append(i)
                    rc += 1
                try:
                    cur.execute("select m_owner_code from machine where machine_name = '{}'".format(currRow[0]))
                    the_code = cur.fetchone()
                    if the_code is not None:
                        the_code = the_code[0]

                    for j in range(len(currRow)):
                        if currRow[j] == '' and self.mach_db[len(self.mach_db) - 1 - rowi][j] == 'None':
                            currRow[j] = 'None'

                    if len(currRow) > 0:
                        # Check against everything but machine status
                        temp_mach_db = self.mach_db[:]
                        for i in range(len(temp_mach_db)):
                            temp_mach_db[i] = temp_mach_db[i][:-1]

                        if currRow in temp_mach_db:
                            # Put empty list in mach_rec if no change from self.mach_db
                            mach_rec.append([])
                        else:
                            # Else append row with new information
                            mach_rec.append(currRow)

                    rowi += 1
                    cur.execute("select * from machine where machine_name = '{}'".format(self.mach_db[-(indx + 1)][0]))
                    machine = cur.fetchone()
                    m_db = []
                    for i in machine:
                        m_db.append(str(i))
                    del m_db[3]
                    mmm_db.append(m_db[1:-1])
                except:
                    return False, [], no_quot, m_allowed_indices

            mach_rec.reverse()

            num_empty = 0
            for i in range(len(mach_rec)):
                if len(mach_rec[i]) == 0:
                    num_empty += 1

            # Check against everything but jlab status
            mmm_db.reverse()
            if mach_rec == [[],[],[]]:
                return False, [], no_quot, m_allowed_indices
            if mmm_db == mach_rec:
                return False, [], no_quot, m_allowed_indices
            else:
                return True, mach_rec, no_quot, m_allowed_indices
        else:
            return False, [], no_quot, []

    def write_changes(self, oBox1, mLB, mbox1, box1, jbox, grid):
        """
        this method reads through the table and writes changes to the database
        :param jlab_num: NOT USED
        :param oBox1: owner info
        :param mbox1: machine info
        :param box1:
        :return:
        """
        # READ FROM LOOKUP SCREEN

        j_emsg = ""
        j_success = False
        m_emsg = ""
        m_success = False

        # List of strings to hold any errors thrown by mySQL statement executions; Used to list errors to user in Popup
        j_errlist = []
        # Dictionary with int (index in jlab_db of changed info) as key and string (changed info) as value
        j_updates = {}
        changed_jlab = False
        j_no_quot = True

        if self.get_selected_jlab() > 0:
            changed_jlab, jlab_rec, j_no_quot, j_allowed_indices = self.rec_j(box1)
            print(changed_jlab)
            if j_no_quot and changed_jlab:
                # UPDATE JLAB INFO IN DB
                # Make change(s) if not equal to JLab list
                cur.execute("START TRANSACTION;")
                for i in range(len(jlab_rec)):
                    if jlab_rec[i] != self.jlab_db[i]:
                        if jlab_rec[i] == '':
                            try:
                                # If user deleted text, then update in database as NULL
                                cur.execute("UPDATE jlabs SET {} = NULL WHERE jlab_number = {}"
                                            .format(self.j_switch(i), self.get_selected_jlab()))
                                self.write_j_history(i, jlab_rec)
                            except mysql.connector.errors.IntegrityError as e:
                                j_errlist.append(str(e))
                        else:
                            try:
                                # else, update user's value
                                cur.execute("UPDATE jlabs SET {} = \"{}\" WHERE jlab_number = {}"
                                            .format(self.j_switch(i), str(jlab_rec[i]),
                                                    self.get_selected_jlab()))
                                self.write_j_history(i, jlab_rec)
                            except mysql.connector.errors.IntegrityError as e:
                                j_errlist.append(str(e))

                        j_updates[i] = jlab_rec[i]

                if len(j_errlist) == 0:
                    for ukey in j_updates.keys():
                        self.jlab_db[ukey] = j_updates[ukey]
                    conn.commit()
                    j_success = True
                else:
                    cur.execute("ROLLBACK;")
                    for i in range(len(j_errlist)):
                        j_emsg += "{}) {}\n".format(i + 1, j_errlist[i])

        # List of lists to hold recalled machine data
        changed_machs, mach_rec, m_no_quot, m_allowed_indices = self.rec_mach(mbox1)

        if m_no_quot:
            # List of strings to hold any errors thrown by mySQL statement executions; Used to list errors to user in Popup
            m_errlist = []
            # Dictionary with tuple (indices in mach_db of changed info) as key and string (changed info) as value
            m_updates = {}

            if changed_machs:
                cur.execute("START TRANSACTION;")
                # WRITE TO DATABASE

                for row in mach_rec:
                    if len(row) > 0:
                        # get machine_code from original (in case the name is what's being changed) name of machine in database
                        curr_m_code = get_m_code(self.mach_db[mach_rec.index(row)][0])
                        #curr_m_code = self.m_code


                        for j in range(len(row)):
                            if row[j] != self.mach_db[mach_rec.index(row)][j]:
                                if row[j] == '':
                                    try:
                                        # If user deleted text, then update in database as NULL
                                        labell = get_columns('machine')
                                        if j > 1:
                                            cur.execute("UPDATE machine "
                                                        "SET {} = NULL "
                                                        "WHERE machine_code = {}".format(labell[j + 2], curr_m_code))
                                            self.write_m_history(j, mach_rec, row, curr_m_code)
                                        else:
                                            cur.execute("UPDATE machine "
                                                        "SET {} = NULL "
                                                        "WHERE machine_code = {}".format(labell[j + 1], curr_m_code))
                                            self.write_m_history(j, mach_rec, row, curr_m_code)
                                    except mysql.connector.errors.IntegrityError as e:
                                        m_errlist.append(str(e))
                                else:
                                    try:
                                        labell = get_columns('machine')
                                        if j > 1:
                                            cur.execute("UPDATE machine "
                                                        "SET {} = \"{}\" "
                                                        "WHERE machine_code = {}".format(labell[j + 2], str(row[j]),
                                                                                         curr_m_code))
                                            self.write_m_history(j, mach_rec, row, curr_m_code)
                                        else:
                                            cur.execute("UPDATE machine "
                                                        "SET {} = \"{}\" "
                                                        "WHERE machine_code = {}".format(labell[j + 1], str(row[j]),
                                                                                         curr_m_code))
                                            self.write_m_history(j, mach_rec, row, curr_m_code)
                                    except mysql.connector.errors.IntegrityError as e:
                                        m_errlist.append(str(e))

                                m_updates[(mach_rec.index(row), j)] = row[j]

                if len(m_errlist) == 0:
                    for ukey in m_updates.keys():
                        self.mach_db[ukey[0]][ukey[1]] = m_updates[ukey]
                    conn.commit()
                    m_success = True
                else:
                    cur.execute("ROLLBACK;")
                    for i in range(len(m_errlist)):
                        m_emsg += "{}) {}\n".format(i + 1, m_errlist[i])
            if j_no_quot:
                self.tell_changes(changed_machs, changed_jlab, j_success, m_success, j_emsg, m_emsg, j_errlist,
                                  m_errlist, oBox1, jbox, mLB, mbox1, grid)

        if not j_no_quot and not m_no_quot:
            self.popup = ErrorQuotesPopup()
            self.popup.children[0].children[0].children[0].children[0].text = "Check JLab and Machine fields."
            self.popup.open()
        elif not m_no_quot:
            self.popup = ErrorQuotesPopup()
            self.popup.children[0].children[0].children[0].children[0].text = "Check Machine fields."
            self.popup.open()
        elif not j_no_quot:
            self.popup = ErrorQuotesPopup()
            self.popup.children[0].children[0].children[0].children[0].text = "Check JLab fields."
            self.popup.open()

    def tell_changes(self, changed_machs, changed_jlab, j_success, m_success, j_emsg, m_emsg, j_errlist, m_errlist,
                     oBox1, jbox, mLb, mbox1, grid):
        """
        Takes in resulting variables of write_changes() method and produces the correct Popup to inform the user of
        successful or failed database changes. Allows user to reset the screen back to original data or go back and
        fix their own errors.
        """
        # UPDATES POPUP
        if changed_machs and changed_jlab:
            # BOTH JLAB AND MACHINES CHANGED
            if j_success and m_success:
                # Use success_popup() to tell user of no detected changes
                self.success_popup("Success!", "All changes saved to the database.")
            elif j_success:
                # Use ErrorResetPopup Class to tell user of error & success
                ptext = "JLab {} changes saved to the database.\n\n".format(self.get_selected_jlab()) \
                        + "Machine Update Error(s):\n" + m_emsg + "\n"
                self.err_res_popup("JLab Success | Machine Error(s)", ptext, oBox1, jbox, mLb, mbox1, grid)
            elif m_success:
                # Use ErrorResetPopup Class to tell user of error & success
                ptext = "JLab Error(s):\n" + j_emsg + "\n\nAll machine changes saved to the database." + "\n"
                self.err_res_popup("JLab Error(s) | Machine Success", ptext, oBox1, jbox, mLb, mbox1, grid)
            else:
                # Use ErrorResetPopup Class to tell user of errors
                ptext = "JLab Error(s):\n" + j_emsg + "\n\nMachine Update Error(s):\n" + m_emsg + "\n"
                self.err_res_popup("Error", ptext, oBox1, jbox, mLb, mbox1, grid)
        elif changed_jlab:
            # JUST CHANGED JLAB
            if j_success:
                # Use success_popup() to tell user of no detected changes
                self.success_popup("Success!",
                                   "JLab {} changes saved to the database.".format(self.get_selected_jlab()))
            else:
                # Use ErrorResetPopup Class to tell user of error
                self.err_res_popup("Error", j_emsg, oBox1, jbox, mLb, mbox1, grid)
        elif changed_machs:
            # JUST CHANGED MACHINES
            if m_success:
                # Use success_popup() to tell user of no detected changes
                self.success_popup("Success!", "All machine changes saved to the database.")
            else:
                # Use ErrorResetPopup Class to tell user of error
                self.err_res_popup("Error", m_emsg, oBox1, jbox, mLb, mbox1, grid)
        else:
            # Use success_popup() to tell user of no detected changes
            self.success_popup("Sorry", "You haven't made any new changes.")

    def write_j_history(self, i, jlab_rec):
        if self.jlab_db[i] != 'RESTRICTED':
            if i == 0:
                vals = (
                    int(self.get_selected_jlab()), str(current_user), 'Changed JLab location', self.jlab_db[i],
                    jlab_rec[i])

                cur.execute(
                    "insert into history( jlab_number, user, changed, prev_data, curr_data) values {}".format(
                        vals))
            if i == 1:
                vals = (int(self.get_selected_jlab()), str(current_user), 'Changed JLab IGSS Version',
                        self.jlab_db[i], jlab_rec[i])
                cur.execute(
                    "insert into history( jlab_number, user, changed, prev_data, curr_data) values {}".format(
                        vals))
            if i == 2:
                vals = (int(self.get_selected_jlab()), str(current_user), 'Changed JLab CCTS Version',
                        self.jlab_db[i], jlab_rec[i])
                cur.execute(
                    "insert into history( jlab_number, user, changed, prev_data, curr_data) values {}".format(
                        vals))
        else:
            pass

    def write_m_history(self, j, mach_rec, row, curr_m_code):
        if self.mach_db[mach_rec.index(row)][j+1] != 'RESTRICTED':
            if j == 0:
                if int(self.get_selected_jlab()) < 1:
                    vals = (int(curr_m_code), str(current_user), 'Changed Machine Name',
                            self.mach_db[mach_rec.index(row)][j], row[j])
                    cur.execute( "insert into history(machine_code, user, changed, prev_data, curr_data) values {}".format(vals))
                else:
                    vals = (int(self.get_selected_jlab()), int(curr_m_code), str(current_user),
                            'Changed Machine Name', self.mach_db[mach_rec.index(row)][j], row[j])
                    cur.execute("insert into history(jlab_number, machine_code, user, changed, prev_data, curr_data) values {}".format( vals))
            if j == 3:
                if int(self.get_selected_jlab()) == -1:
                    # Let jlab_number be NULL if unattached machine
                    vals = (int(curr_m_code), str(current_user), 'Changed Machine IP',
                            self.mach_db[mach_rec.index(row)][j+1], row[j])
                    cur.execute( "insert into history(machine_code, user, changed, prev_data, curr_data) values {}".format( vals))

                else:
                    vals = (int(self.get_selected_jlab()), int(curr_m_code), str(current_user),
                            'Changed Machine IP', self.mach_db[mach_rec.index(row)][j+1], row[j])
                    cur.execute(
                        "insert into history(jlab_number, machine_code, user, changed, prev_data, curr_data) values {}".format(
                            vals))
        else:
            pass

    def success_popup(self, title, msg):
        self.popup = Popup()
        self.popup.title = title
        self.popup.content = Label(text=msg)
        self.popup.size_hint = (None, None)
        self.popup.size = (len(msg) * 8, 100)
        self.popup.auto_dismiss = True
        self.popup.open()

    def err_res_popup(self, title, msg, oBox1, jbox, mLb, mbox1, grid):
        self.popup = ErrorResetPopup()

        self.popup.title = title
        self.popup.children[0].children[0].children[0].children[2].children[0].text = msg

        self.popup.children[0].children[0].children[0].children[1].bind(on_release=lambda x: self.conf_popup(0))
        self.popup.children[0].children[0].children[0].children[0].bind(
            on_press=lambda y: self.refresh_table(self.get_selected_jlab(), oBox1, jbox, mLb, mbox1, grid))
        self.popup.children[0].children[0].children[0].children[0].bind(on_release=lambda z: self.conf_popup(1))

        self.popup.open()

    def conf_popup(self, btn_num):
        self.popup = ConfPopup()

        if btn_num == 0:
            self.popup.content = Label(text="Please fix your errors in\norder to write to the database.",
                                       halign='center')
            self.popup.size = (300, 150)
        else:
            self.popup.content = Label(text="Data reset to last valid \n state before changes.",
                                       halign='center')
            self.popup.size = (250, 150)

        self.popup.open()

    def j_switch(self, index):
        """
        makes a switch statement from Machine table (minus machine_code) to be used in write_changes() to identify
        which Machine field(s) have been changed...returns column name of changed field(s)
        :param arg: index (in both list and switch) of changed field
        :return: column name of changed field
        """
        global test_schema

        j_columns = copy.deepcopy(test_schema["jlabs"])
        del j_columns[0]
        del j_columns[4]

        switch = {}
        for i in range(len(j_columns)):
            switch[i] = j_columns[i]

        return switch.get(index, "nothing")

    def m_switch(self, arg):
        """
        makes a switch statement from Machine table (minus machine_code) to be used in write_changes() to identify
        which Machine field(s) have been changed...returns column name of changed field(s)
        :param arg: index (in both list and switch) of changed field
        :return: column name of changed field
        """
        global test_schema

        m_columns = copy.deepcopy(test_schema["machine"])
        # del m_columns[0]

        switch = {}
        for i in range(len(m_columns)):
            switch[i] = m_columns[i]

        return switch.get(arg, "nothing")

    def get_o_code(self, o_name):
        cur.execute("SELECT owner_code FROM owner WHERE owner_name = \"{}\";".format(str(o_name)))
        o_code = int(cur.fetchone()[0])

        return o_code

    def deselect(self, grid):
        """calls the deselect all method from the SelectableGrid class"""
        grid.deselect_all_nodes(grid)
        self.children[1].children[1].children[0].children[2].children[1].text = ''

    def ownerOptions(self, btn):
        self.popup = OwnerPopup()
        self.popup.open()
        self.popup.getJLab(self.num)

    def changeStat(self, mOrj, status, code, box, btn):
        global privileges_strings

        self.popup = StatusPopup()
        opposite = 'active'
        type = "JLab's "

        if mOrj == 'm':
            cur.execute("Select {} from machine where machine_code = {}".format(privileges_strings["machine"], code))
            mach = cur.fetchone()
            status = mach[-1]
        elif mOrj == 'j':
            cur.execute("Select {} from jlabs where jlab_number = {}".format(privileges_strings["jlabs"], code))
            jlab = cur.fetchone()
            status = jlab[-1]

        if status == 'active':
            opposite = 'inactive'
        if mOrj == 'm':
            type = "Machine's "
        self.popup.getCode(code, box, mOrj)
        self.popup.title = "This " + type + "status is " + status + '\n Would you like to change it to ' + opposite + '?'
        self.popup.open()

    def compOwner(self, contact, machine, box, btn):
        self.popup = MachineOwnerPopup()
        cur.execute("select * from machine where machine_name = '{}'".format(machine))
        try:
            m = cur.fetchone()[0]
        except TypeError:
            m = machine
        self.popup.get_info(contact, m)
        self.popup.open()

    def compOwnerJ(self, contact, machine, box, btn):
        self.popup = MachineOwnerPopup()
        self.popup.get_info(contact, machine)
        self.popup.open()

    def ReadInput(self):
        """method allows users to type jlab number and lookup instead of scrolling through jlabs """
        SelectedJlab = (self.children[1].children[1].children[0].children[2].children[1].text)
        grid = self.children[1].children[1].children[0].children[0].children[0]
        abc = 0
        grid.deselect_all_nodes(grid)
        for a in self.children[1].children[1].children[0].children[0].children[0].children:
            if str(a.text) == str(SelectedJlab):
                grid.select_node(a)
                abc = 1
        if abc == 0:
            if SelectedJlab != '':
                self.popup = LookupErrorPopup()
                self.popup.open()


class AdvancedLookupScreen(Screen):
    # create empty label dictionary
    l_dict = {}
    searched = None
    tooltip_adv = Tooltip(text='Hello world')
    tis_adv = []

    # TOOLTIP METHODS
    def __init__(self, **kwargs):
        Window.bind(mouse_pos=self.on_mouse_pos)
        super(Screen, self).__init__(**kwargs)

    def on_mouse_pos(self, *args):
        if not self.get_root_window():
            return
        pos = args[1]
        self.tooltip_adv.pos = pos
        x = self.tooltip_adv.pos[0] - self.tooltip_adv.size[0]
        self.tooltip_adv.pos = (x, self.tooltip_adv.pos[1])
        Clock.unschedule(self.display_tooltip)  # cancel scheduled event since I moved the cursor
        self.close_tooltip()  # close if it's opened
        for i in self.tis_adv:
            if Label(pos=i.to_window(*i.pos), size=i.size).collide_point(*self.to_widget(*pos)):
                self.tooltip_adv.text = i.text
                Clock.schedule_once(self.display_tooltip, 1)

    def close_tooltip(self, *args):
        Window.remove_widget(self.tooltip_adv)

    def display_tooltip(self, *args):
        Window.add_widget(self.tooltip_adv)

    # END TOOLTIP METHODS

    def popOwnerProgram(self, btn):
        self.popup = OwnerPopup2()
        self.popup.open()

    # create each check box/label/textinput based on the labels
    def makeLevels(self, base):
        """
        creates checlboxes, labels, and textinputs for jlab search options
        :param base: boylayout holding options
        :return: None
        """
        global test_schema
        # Get JLab labels
        j_labels = copy.deepcopy(test_schema["jlabs"])
        temp = copy.deepcopy(j_labels)
        missing_indices = null_user_restrictions("jlabs", temp)[1]
        # del j_labels[6]

        for lab in j_labels:
            if lab in dbDict:
                j_labels[j_labels.index(lab)] = dbDict[lab]

        for i in range(len(j_labels)):
            b = BoxLayout(orientation='horizontal', size_hint=(0.9, 1), pos_hint={'center_x': 0.5})

            if i in missing_indices:
                # If restricted, disable checkbox for field
                b.add_widget(CheckBox(size_hint=(.02, 1), readonly=True, disabled=True))
            else:
                b.add_widget(CheckBox(size_hint=(.02, 1)))

            b.add_widget(Label(text=j_labels[i], size_hint=(.2, 1), halign='left'))

            if i in missing_indices:
                # If restricted, disable textinput for field
                b.add_widget(TextInput(size_hint=(.5, .6), pos_hint={'center_y': 0.5}, readonly=True, disabled=True))
            elif j_labels[i] == 'Owner Info:':
                # b.add_widget(Label(size_hint= (.5,1)))
                owner_stuff = BoxLayout(orientation='horizontal', size_hint=(.5, .5),
                                        pos_hint={'top': .717, 'center_x': .575})
                selectBTN = Button(size_hint=(.3, 1), text='Select')
                owner_stuff.add_widget(selectBTN)
                selectBTN.bind(on_release=partial(self.popOwnerProgram))
                baby1 = BoxLayout(size_hint=(.2, 1.2), orientation='vertical')
                baby1.add_widget(Label(text='Name:'))
                baby1.add_widget(Label(text='Email:'))
                baby1.add_widget(Label(text='Number:'))
                owner_stuff.add_widget(baby1)
                ownerI = BoxLayout(size_hint=(.5, 1.2), orientation='vertical', id='ownerI')
                nameLabel = Label(text='')
                ownerI.add_widget(nameLabel)
                ownerI.add_widget(Label(text=''))
                ownerI.add_widget(Label(text=''))
                owner_stuff.add_widget(ownerI)
                b.add_widget(owner_stuff)
            elif j_labels[i] == 'JLab Status':
                b.add_widget(TextInput(size_hint=(.5, .6), pos_hint={'center_y': 0.5}, hint_text='active/inactive',
                                       write_tab=False, multiline=False))
            else:
                b.add_widget(
                    TextInput(size_hint=(.5, .6), pos_hint={'center_y': 0.5}, write_tab=False, multiline=False))
            base.add_widget(b)

    # reads in text from textinputs: creates dictionary for info
    def getStuff(self, base):
        """
        retrieves text inputs from jlab options, creates dictionary
        :param base: boylayout hilding check boxes and textinputs
        :return: None
        """
        self.l_dict = {}
        # listOrNot has identical keys as l_dict, but its values tell it each value is is list (T/F)
        listOrNot = {}
        for level in base.children:
            x = level.children
            if x[-1].active:
                nameLabel = self.children[1].children[0].children[0].children[3].children[0].children[0].children[2]
                if x[-2].text == 'Owner Info:':
                    if nameLabel.text != '':
                        self.l_dict[x[-2].text] = nameLabel.text
                        listOrNot[x[-2].text] = False
                elif x[0].text != '':
                    entry_l = x[0].text.split(';')
                    new_l = []
                    for i in entry_l:
                        i = i.strip()
                        new_l.append(str(i))
                    if len(entry_l) > 1:
                        # if the text input contains more than one search value, add tuple to the dict
                        self.l_dict[x[-2].text] = tuple(new_l)
                        listOrNot[x[-2].text] = True
                    else:
                        # else just add the text
                        self.l_dict[x[-2].text] = str(x[0].text)
                        listOrNot[x[-2].text] = False
        if len(self.l_dict) == 0:
            print('error')
        return self.l_dict, listOrNot

    # popup for invalid range in a lookup textinput
    def invalidRangePopup(self):
        self.popup = ErrorPopup()
        self.popup.open()

    # clears all pressed checkboxes as well as text inputs
    def clearSelections(self, base, sbox):
        """
        clears entire screen, including check boxes, text inputs, and table
        :param base: boylayout holding check boxes and text inputs
        :param sbox: boylayout holding table of jlabs
        :param jbox: boxlayout holding sbox
        :return:
        """
        for level in base.children:
            x = level.children
            if x[-1].active:
                x[-1].active = False
            if base.children.index(level) == 3:
                for lab in x[0].children[0].children:
                    lab.text = ''
            else:
                x[0].text = ''
        # for each in owner.children:
        #     each.text = ''
        self.l_dict = {}
        sbox.clear_widgets()

    def clearTable(self, sbox, jbox):
        """
        clears jlab table
        :param sbox: boylayout holding table of jlabs
        :param jbox: boxlayout holding sbox
        :return: None
        """
        jbox.clear_widgets()
        sbox.clear_widgets()

    def createTable(self, sbox, jbox, lb, base, orID, andID, notID, ):
        """method to create a table holding info about the currently selected jlab
        This defaults to no jlab being selected, and thus the JLabs info is N/A
        :param: box: row of textinputs
        :param: lb: labels of jLab info"""
        global privileges_strings
        global test_schema
        # clear old table before building new one
        self.searched = None
        try:
            # clear widgets so the table can be remade
            sbox.clear_widgets()
            sel_list = []
            x, is_list = self.getStuff(base)
            if len(x) == 0:
                self.popup = CheckPopup()
                self.popup.open()
            else:
                if notID.state == 'down':
                    ex = "SELECT {} FROM jlabs WHERE NOT ".format(privileges_strings["jlabs"])
                else:
                    ex = "SELECT {} FROM jlabs WHERE ".format(privileges_strings["jlabs"])
                if 'Owner Info:' in x:
                    if x['Owner Info:'] != None:
                        cur.execute("select {} from owner where owner_name = \"{}\"".format(privileges_strings["owner"],
                                                                                            str(x.get('Owner Info:'))))
                        o = cur.fetchone()
                        temp = list(o)
                        o_code = temp[0]
                        x['Owner Info:'] = o_code
                    elif 'Owner Info:' == 'None':
                        x['Owner Info:'] = None
                form = []
                count = 0
                checked = []
                for i in x:
                    n = ''
                    if i == "Owner Info:":
                        n = "owner_code"
                    elif i == "JLab Status":
                        n = 'j_status'
                    elif i == 'JLab #':
                        n = 'jlab_number'
                    else:
                        for char in i:
                            if char == ' ':
                                char = '_'
                            n += char
                    checked.append(n)
                    if count < len(x) - 1:
                        # if the search values are in a list, use IN
                        if is_list[i]:
                            # queries change based on which toggle button is pressed
                            if andID.state == 'down':
                                ex += n.lower() + " IN {} and "
                            elif orID.state == 'down':
                                ex += n.lower() + " IN {} or "
                            elif notID.state == 'down':
                                ex += n.lower() + " IN {} and not "
                        else:
                            if andID.state == 'down':
                                if x.get(i) == None or i == 'Owner Info:' and x.get(i) == 'None':
                                    ex += n.lower() + " IS {} and "
                                else:
                                    ex += n.lower() + " = \"{}\" and "
                            elif orID.state == 'down':
                                if x.get(i) == None or i == 'Owner Info:' and x.get(i) == 'None':
                                    ex += n.lower() + " IS {} or "
                                else:
                                    ex += n.lower() + " = \"{}\" or "
                            elif notID.state == 'down':
                                if x.get(i) == None or i == 'Owner Info:' and x.get(i) == 'None':
                                    ex += n.lower() + " IS {} and not "
                                else:
                                    ex += n.lower() + " = \"{}\" and not "
                    else:
                        # if you are on the last part of the query, don't include 'and' at the end
                        if is_list[i]:
                            ex += n.lower() + " IN {}"
                        else:
                            if x.get(i) == None or i == 'Owner Info:' and x.get(i) == 'None':
                                ex += n.lower() + " IS {}"
                            else:
                                ex += n.lower() + " = \"{}\""
                    # add to the list of formatted values to be put into the query string
                    if i == 'Owner Info:' and x.get(i) == 'None':
                        form.append('NULL')
                    elif x.get(i) is None:
                        form.append('NULL')
                    else:
                        form.append(x.get(i))
                    count += 1

                nullQ = 'SELECT {} FROM jlabs WHERE '.format(privileges_strings["jlabs"])
                c = 0
                for a in checked:
                    if a == 'owner_code' and x.get('Owner Info:') == 'None':
                        pass
                    else:
                        if c < len(checked) - 1:
                            nullQ += a.lower() + ' is NULL or '
                        else:
                            nullQ += a.lower() + ' is NULL'
                    c += 1
                if 'NULL' in nullQ:
                    cur.execute(nullQ)
                    nulls = cur.fetchall()

                # creates list of selected jlabs by querying db
                if x != {}:
                    cur.execute(ex.format(*form))
                    rows = cur.fetchall()
                    self.searched = copy.deepcopy(list(rows))
                    if notID.state == 'down':
                        try:
                            for i in nulls:
                                rows.append(i)
                        except UnboundLocalError:
                            pass
                            # means there was nothing with NULL queried
                    for row in rows:
                        l = []
                        for i in row:
                            l.append(str(i))
                        l, missing_js_indices = null_user_restrictions("jlabs", l)

                        sel_list.append(l)

                    jLabels = copy.deepcopy(test_schema["jlabs"])
                    # Remove jlab_number field
                    # del jLabels[0]
                    # creates label row for jlabs
                    if lb.children == []:
                        for lab in jLabels:
                            if lab == 'owner_code':
                                lb.add_widget(Label(text='Owner Name', halign='center'))
                            else:
                                lb.add_widget(Label(text=dbDict[lab], halign='center'))

                    # builds jlab table
                    sbox.size = (400, len(sel_list) * 40)
                    b = BoxLayout(orientation='horizontal')
                    sbox.add_widget(b)
                    for row in range(len(sel_list)):
                        j_code = sel_list[row][0]
                        # del sel_list[row][0]
                        o_code = sel_list[row][5]
                        if o_code != 'None':
                            cur.execute("select * from owner where owner_code= \"{}\"".format(o_code))
                            o = cur.fetchone()
                            sel_list[row][5] = o[1]
                        # for item in range(len(sel_list[row])):
                        #     if item in missing_js_indices:
                        #         b.add_widget(TextInput(text=sel_list[row][item], readonly=True, disabled=True))
                        #     elif jLabels[item] == 'jlab_comments':
                        #         # these are boxes which need tooltips
                        #         if sel_list[row][item] == 'None':
                        #             ti = MyTextInput(text='', readonly=True, disabled=True, disabled_foreground_color=(0, 0, 0, 1))
                        #         else:
                        #             ti = MyTextInput(text=sel_list[row][item], readonly=True, disabled=True,
                        #                              disabled_foreground_color=(0, 0, 0, 1))
                        #         self.tis_adv.append(ti)
                        #         b.add_widget(ti)
                        #     elif jLabels[item] == 'j_status':
                        #         statusBox5 = BoxLayout(padding=5, spacing=5)
                        #         status = Label(text=sel_list[row][item])
                        #         statBTN = Button(text='change')
                        #         statBTN.bind(
                        #             on_release=partial(self.changeStat, 'j', sel_list[row][item], j_code, statusBox5))
                        #         statusBox5.add_widget(status)
                        #         statusBox5.add_widget(statBTN)
                        #         b.add_widget(statusBox5)
                        #     else:
                        #         if sel_list[row][item] == 'None':
                        #             b.add_widget(TextInput(text='', readonly=True, disabled=True,
                        #                                    disabled_foreground_color=(0, 0, 0, 1)))
                        #         else:
                        #             b.add_widget(TextInput(text=sel_list[row][item], readonly=True, disabled=True,
                        #                                    disabled_foreground_color=(0, 0, 0, 1)))
                        # b = BoxLayout(orientation='horizontal')
                        # if row < len(sel_list) - 1:
                        #     sbox.add_widget(b)
                        for item in range(len(sel_list[row])):
                            if item == 7:
                                # these are boxes which need tooltips
                                if sel_list[row][item] == 'None':
                                    ti = MyTextInput(text='', readonly=True, disabled=True, disabled_foreground_color=(0, 0, 0, 1))
                                else:
                                    ti = MyTextInput(text=sel_list[row][item], readonly=True, disabled=True,
                                                     disabled_foreground_color=(0, 0, 0, 1))
                                self.tis_adv.append(ti)
                                b.add_widget(ti)
                            elif item == 8:
                                statusBox5 = BoxLayout(padding=5, spacing=5)
                                status = Label(text=sel_list[row][item])
                                statBTN = Button(text='change')
                                statBTN.bind(
                                    on_release=partial(self.changeStat, 'j', sel_list[row][item], j_code, statusBox5))
                                statusBox5.add_widget(status)
                                statusBox5.add_widget(statBTN)
                                b.add_widget(statusBox5)
                            else:
                                if sel_list[row][item] == 'None':
                                    b.add_widget(
                                        TextInput(text='', readonly=True, disabled=True, disabled_foreground_color=(0, 0, 0, 1)))
                                else:
                                    b.add_widget(TextInput(text=sel_list[row][item], readonly=True, disabled=True,
                                                           disabled_foreground_color=(0, 0, 0, 1)))
                        b = BoxLayout(orientation='horizontal')
                        if row < len(sel_list) - 1:
                            sbox.add_widget(b)
        except ReferenceError:
            pass

    def changeStat(self, mOrj, status, code, box, btn):
        global privileges_strings
        self.popup = StatusPopup()
        opposite = 'active'
        type = "JLab's "

        if mOrj == 'm':
            cur.execute("Select {} from machine where machine_code = {}".format(privileges_strings["machine"], code))
            mach = cur.fetchone()
            status = mach[-1]
        elif mOrj == 'j':
            cur.execute("Select {} from jlabs where jlab_number = {}".format(privileges_strings["jlabs"], code))

        if status == 'active':
            opposite = 'inactive'
        if mOrj == 'm':
            type = "Machine's "
        self.popup.getCode(code, box, mOrj)
        self.popup.title = "This " + type + "status is " + status + '\n Would you like to change it to ' + opposite + '?'
        self.popup.open()

    def generateReport(self):
        try:
            if len(self.searched) > 0:
                popup = SaveDialog(self)
                popup.srchd = self.searched
                popup.srchd_table = "jlabs"
                popup.open()
            else:
                popup = Popup(title="Sorry...", size_hint=(None, None), size=(175, 100),
                              content=Label(text='No results to save.'))
                popup.open()
        except:
            popup = Popup(title="Sorry...", size_hint=(None, None), size=(175, 100),
                          content=Label(text='No results to save.'))
            popup.open()


class MachineLookupScreen(Screen):
    # create label list and empty label dictionary
    l_dict = {}
    searched = None
    tooltip_m = Tooltip(text='Hello world')
    tis_m = []
    the_row = 0

    def __init__(self, **kwargs):
        Window.bind(mouse_pos=self.on_mouse_pos)
        super(Screen, self).__init__(**kwargs)

    def on_mouse_pos(self, *args):
        if not self.get_root_window():
            return
        pos = args[1]
        self.tooltip_m.pos = pos
        x = self.tooltip_m.pos[0] - self.tooltip_m.size[0]
        self.tooltip_m.pos = (x, self.tooltip_m.pos[1])
        Clock.unschedule(self.display_tooltip)  # cancel scheduled event since I moved the cursor
        self.close_tooltip()  # close if it's opened
        for i in self.tis_m:
            if Label(pos=i.to_window(*i.pos), size=i.size).collide_point(*self.to_widget(*pos)):
                self.tooltip_m.text = i.text
                Clock.schedule_once(self.display_tooltip, 1)

    def close_tooltip(self, *args):
        Window.remove_widget(self.tooltip_m)

    def getId(self, id):
        self.idd = id

    def display_tooltip(self, *args):
        Window.add_widget(self.tooltip_m)

        # create each check box/label/textinput based on the labels

    def makeLevels(self, base):
        global test_schema

        m_labels = copy.deepcopy(test_schema["machine"])
        temp = copy.deepcopy(m_labels)
        missing_indices = null_user_restrictions("machine", temp)[1]
        del m_labels[0]
        # Shift indices to account for machine_code and m_owner_code deletion
        for i in range(len(missing_indices)):
            missing_indices[i] -= 2

        for lab in m_labels:
            if lab in dbDict:
                m_labels[m_labels.index(lab)] = dbDict[lab]

        for i in range(len(m_labels)):
            b = BoxLayout(orientation='horizontal', size_hint=(0.9, 1), pos_hint={'center_x': 0.5})

            if i in missing_indices:
                # If restricted, disable checkbox for field
                b.add_widget(CheckBox(size_hint=(.1, 1), readonly=True, disabled=True))
            else:
                b.add_widget(CheckBox(size_hint=(.1, 1)))

            b.add_widget(Label(text=m_labels[i], size_hint=(.2, 1), halign='left'))

            if i in missing_indices:
                # If restricted, disable textinput for field
                b.add_widget(TextInput(size_hint=(.5, .6), pos_hint={'center_y': 0.5}, readonly=True, disabled=True))
            elif m_labels[i] == 'Machine Status':
                b.add_widget(TextInput(size_hint=(.5, .6), pos_hint={'center_y': 0.5},
                                       hint_text='active/inactive', write_tab=False, multiline=False))
            elif m_labels[i] == 'Machine Owner':
                owner_stuff = BoxLayout(orientation='horizontal', size_hint=(.5, .6), pos_hint={'center_y': 0.5})
                selectBTN = Button(size_hint=(.3, 1), text='Select')
                owner_stuff.add_widget(selectBTN)
                selectBTN.bind(on_release=partial(self.popOwnerProgram, owner_stuff))
                baby1 = BoxLayout(size_hint=(.2, 1), orientation='vertical')
                baby1.add_widget(Label(text='Name:'))
                owner_stuff.add_widget(baby1)
                ownerI = BoxLayout(size_hint=(.5, 1), orientation='vertical', id='ownerI')
                nameLabel = Label(text='')
                ownerI.add_widget(nameLabel)
                owner_stuff.add_widget(ownerI)
                b.add_widget(owner_stuff)
            else:
                b.add_widget(
                    TextInput(size_hint=(.5, .6), pos_hint={'center_y': 0.5}, write_tab=False, multiline=False))
            base.add_widget(b)

    # reads in text from textinputs: creates dictionary for info
    def getMStuff(self, base):
        self.l_dict = {}
        # listOrNot has identical keys as l_dict, but its values tell it each value is is list (T/F)
        listOrNot = {}
        for level in base.children:
            x = level.children
            if x[-1].active:
                try:
                    if x[0].text != '':
                        entry_l = x[0].text.split(';')
                        new_l = []
                        for i in entry_l:
                            i = i.strip()
                            new_l.append(str(i))
                        label = x[-2].text.lower()
                        # change label text to match database column names
                        if '#' in label:
                            label = label.replace('#', 'number')
                            if 'machine ' in label:
                                label = label.replace('machine ', '')
                        elif label == 'specifications':
                            label = 'specs'
                        elif 'status' in label:
                            label = 'm_status'
                        elif label == 'company':
                            label = 'machine_company'
                        if len(entry_l) > 1:
                            # if the text input contains more than one search value, add tuple to the dict
                            self.l_dict[label] = tuple(new_l)
                            listOrNot[label] = True
                        else:
                            # else just add the text
                            self.l_dict[label] = str(x[0].text)
                            listOrNot[label] = False
                except AttributeError:
                    #name = x[0].children[0].children[0].children[0].text
                    label = x[-2].text.lower()
                    name= x[0].children[0].children[0].text
                    cur.execute("select owner_code from owner where owner_name = '{}'".format(name))
                    o_code = cur.fetchone()[0]
                    self.l_dict[label] = int(o_code)
                    listOrNot[label] = False
        return self.l_dict, listOrNot

    # popup for invalid range in a lookup textinput
    def invalidRangePopup(self):
        self.popup = ErrorPopup()
        self.popup.open()

    # clears all pressed checkboxes as well as text inputs
    def clearSelections(self, base, mbox, smbox):
        """
        clears entire screen, including check boxes, text inputs, and table
        :param base: boylayout holding check boxes and text inputs
        :param sbox: boylayout holding table of jlabs
        :param jbox: boxlayout holding sbox
        :return:
        """
        for level in base.children:
            x = level.children
            if x[-1].active:
                x[-1].active = False
            if len(x) > 3:
                x[2].text = ''
                x[0].text = ''
            else:
                x[0].text = ''
        self.l_dict = {}
        mbox.clear_widgets()

    def clearTable(self, mbox, smbox):
        """
        clears jlab table
        :param sbox: boylayout holding table of jlabs
        :param jbox: boxlayout holding sbox
        :return: None
        """
        smbox.clear_widgets()
        mbox.clear_widgets()

    def createMTable(self, mbox, smbox, lb, mbase, mOr, mAnd, mNot):
        """method to create a table holding info about the currently selected jlab
        This defaults to no jlab being selected, and thus the JLabs info is N/A
        :param: box: row of textinputs
        :param: lb: labels of jLab info"""
        global privileges_strings
        global test_schema
        # clear old table before building new one
        self.searched = None
        mbox.clear_widgets()
        lb.clear_widgets()
        smbox = BoxLayout()
        mbox.add_widget(smbox)

        sel_list = []
        x, is_list = self.getMStuff(mbase)
        if len(x) == 0:
            self.popup = CheckPopup()
            self.popup.open()
        else:
            if mNot.state == 'down':
                ex = "SELECT {} FROM machine WHERE NOT ".format(privileges_strings["machine"])
            else:
                ex = "SELECT {} FROM machine WHERE ".format(privileges_strings["machine"])
            form = []
            count = 0
            checked = []
            for i in x:
                n = ''
                if i == 'machine owner':
                    n= 'm_owner_code'
                else:
                    for char in i:
                        if char == ' ':
                            char = '_'
                        n += char
                checked.append(n)
                if count < len(x) - 1:
                    # if the search values are in a list, use IN
                    # queries change based on which toggle button is pressed
                    if is_list[i]:
                        if mAnd.state == 'down':
                            ex += n.lower() + " IN {} and "
                        elif mOr.state == 'down':
                            ex += n.lower() + " IN {} or "
                        elif mNot.state == 'down':
                            ex += n.lower() + " IN {} and NOT "
                    else:
                        if n.lower() == 'm_owner_code':
                            if mAnd.state == 'down':
                                ex += n.lower() + " = {} and "
                            elif mOr.state == 'down':
                                ex += n.lower() + " = {} or "
                            elif mNot.state == 'down':
                                ex += n.lower() + " = {} and NOT "
                        else:
                            if mAnd.state == 'down':
                                ex += n.lower() + " = \"{}\" and "
                            elif mOr.state == 'down':
                                ex += n.lower() + " = \"{}\" or "
                            elif mNot.state == 'down':
                                ex += n.lower() + " = \"{}\" and NOT "
                else:
                    # if you are on the last part of the query, don't include 'and' at the end
                    if is_list[i]:
                        ex += n.lower() + " IN {}"
                    else:
                        if n.lower() == 'm_owner_code':
                            ex += n.lower() + " = {}"
                        else:
                            ex += n.lower() + " = \"{}\""
                # add to the list of formatted values to be put into the query string
                form.append(x.get(i))
                count += 1

            nullQ = 'SELECT {} FROM machine WHERE '.format(privileges_strings["machine"])
            c = 0
            for a in checked:
                if a == 'machine_owner':
                    a= 'm_owner_code'
                if c < len(checked) - 1:
                    nullQ += a + ' is NULL or '
                else:
                    nullQ += a + ' is NULL'
                c += 1
            cur.execute(nullQ)
            nulls = cur.fetchall()

            # creates list of selected jlabs by querying db
            if x != {}:
                # creates list of selected machines
                cur.execute(ex.format(*form))
                rows = cur.fetchall()
                self.searched = copy.deepcopy(list(rows))
                if mNot.state == 'down':
                    for i in nulls:
                        rows.append(i)
                for row in rows:
                    l = []
                    for i in row:
                        l.append(str(i))
                    sel_list.append(l)

                b = smbox
                b.size_hint = 1, 0
                # mLabels = get_columns("Machine")
                mLabels = copy.deepcopy(test_schema["machine"])

                # Remove m_code field
                del mLabels[0]
                mLabels.insert(0, 'JLab')

                lb.add_widget(Label(text=mLabels[0]))
                # creates label row for machs
                for lab in mLabels:
                    # Skip 'JLab' since not in dbDict
                    if lab == 'm_owner_code':
                        pass
                    elif mLabels.index(lab) > 0:
                        lb.add_widget(Label(text=dbDict[lab], halign='center'))

                # builds mlab table
                mbox.size = (400, len(sel_list) * 40)
                b = BoxLayout(orientation='horizontal')
                mbox.add_widget(b)

                for row in range(len(sel_list)):
                    cur.execute('select {} from hardware where machine_code = {}'.format(privileges_strings["hardware"],
                                                                                         sel_list[row][0]))
                    jlab = cur.fetchall()
                    try:
                        jlabOpt = BoxLayout(padding=5, spacing=5)
                        jlabOpt.add_widget(Label(size_hint=(.2, 1), text=str(jlab[0][0])))
                    except:
                        jlabOpt.add_widget(Label(size_hint=(.2, 1), text=""))

                    eBtn = Button(size_hint=(.8, 1), text='change JLab')
                    self.popup = ChangeLinkPopup()
                    x = self.popup

                    # eBtn.bind(on_press= self.changeLink)
                    eBtn.bind(on_press=partial(self.changeLink, sel_list[row], jlabOpt))
                    jlabOpt.add_widget(eBtn)
                    b.add_widget(jlabOpt)
                    curr_row, missing_indices = null_user_restrictions("machine", sel_list[row])
                    for item in range(1, len(curr_row)):
                        if item in missing_indices:
                            b.add_widget(TextInput(text=curr_row[item], readonly=True, disabled=True))
                        elif mLabels[item] == 'machine_comments':
                            if curr_row[item] == 'None':
                                ti = MyTextInput(text='', readonly=True, disabled=True, disabled_foreground_color=(0, 0, 0, 1))
                            else:
                                ti = MyTextInput(text=curr_row[item], readonly=True, disabled=True,
                                                 disabled_foreground_color=(0, 0, 0, 1))
                            self.tis_m.append(ti)
                            b.add_widget(ti)
                        elif mLabels[item] == 'm_status':
                            statusBox6 = BoxLayout(padding=5)
                            status = Label(text=curr_row[item])
                            statBTN = Button(text='change')
                            statBTN.bind(
                                on_release=partial(self.changeStat, 'm', curr_row[item], curr_row[0], statusBox6))
                            statusBox6.add_widget(status)
                            statusBox6.add_widget(statBTN)
                            b.add_widget(statusBox6)
                        elif mLabels[item] == 'machine_company':
                            compBox = BoxLayout()
                            if sel_list[row][item] == 'None':
                                comp = TextInput(text='',write_tab=False, readonly=True, disabled=True, disabled_foreground_color=(0, 0, 0, 1))
                            else:
                                comp = TextInput(text=sel_list[row][item],write_tab=False, readonly=True, disabled=True,
                                                 disabled_foreground_color=(0, 0, 0, 1))
                            compBTN = Button(text='+', size_hint=(.2, 1))
                            compBTN.bind(on_release=partial(self.display_owner, sel_list[row][3]))
                            compBox.add_widget(comp)
                            compBox.add_widget(compBTN)
                            b.add_widget(compBox)
                        elif mLabels[item] == 'm_owner_code':
                            pass
                        else:
                            if curr_row[item] == 'None':
                                b.add_widget(TextInput(text='', readonly=True, disabled=True, disabled_foreground_color=(0, 0, 0, 1)))
                            else:
                                b.add_widget(TextInput(text=curr_row[item], readonly=True, disabled=True,
                                                       disabled_foreground_color=(0, 0, 0, 1)))
                    b = BoxLayout(orientation='horizontal')
                    if row < len(sel_list) - 1:
                        mbox.add_widget(b)

    def changeLink(self, r, jlabOpt, btn):
        """
        calls popup to change what jlab a machine is linked to
        :param m: machine selected
        :return: None
        """
        self.popup = ChangeLinkPopup()
        self.popup.getM(r)
        self.popup.getBox(jlabOpt)
        self.popup.open()

    def changeStat(self, mOrj, status, code, box, btn):
        global privileges_strings

        self.popup = StatusPopup()
        opposite = 'active'
        type = "JLab's "

        if mOrj == 'm':
            cur.execute("Select {} from machine where machine_code = {}".format(privileges_strings["machine"], code))
            mach = cur.fetchone()
            status = mach[-1]
        elif mOrj == 'j':
            cur.execute("Select {} from jlabs where jlab_number = {}".format(privileges_strings["jlabs"], code))
            jlab = cur.fetchone()
            status = jlab[-1]

        if status == 'active':
            opposite = 'inactive'
        if mOrj == 'm':
            type = "Machine's "
        self.popup.getCode(code, box, mOrj)
        self.popup.title = "This " + type + "status is " + status + '\n Would you like to change it to ' + opposite + '?'
        self.popup.open()

    def generateReport(self):
        try:
            if len(self.searched) > 0:
                popup = SaveDialog(self)
                popup.srchd = self.searched
                popup.srchd_table = "machine"
                popup.open()
            else:
                popup = Popup(title="Sorry...", size_hint=(None, None), size=(175, 100),
                              content=Label(text='No results to save.'))
                popup.open()
        except:
            popup = Popup(title="Sorry...", size_hint=(None, None), size=(175, 100),
                          content=Label(text='No results to save.'))
            popup.open()

    def display_owner(self, o_code, btn):
        try:
            cur.execute('select * from owner where owner_code = {}'.format(o_code))
            info = cur.fetchone()
            for i in range(len(info)):
                if info[i] is None:
                    info[i] = 'None'
        except:
            info = [0, "None", "None", "None"]
        self.popup = Popup(title='COMPANY CONTACT', size_hint=(None, None), size=(400, 300))
        labs = ['Name:', "Email:", "Phone:"]
        b = BoxLayout(orientation='vertical')
        for i in range(len(labs)):
            n = BoxLayout()
            n.add_widget(Label(text=labs[i]))
            n.add_widget(Label(text=info[i + 1]))
            b.add_widget(n)
        self.popup.add_widget(b)
        self.popup.open()

    def popOwnerProgram(self,box ,btn):
        self.popup = OwnerPopup2()
        self.popup.get_machine(box, True)
        self.popup.open()


class AddScreen(Screen):
    """"class for the Add JLabs screen"""

    def addMachines(self, g):
        pass

    def popAddLab(self):
        """method to create popup for adding a JLab with options for what to do next """
        self.popup = AddLabPopup()
        self.popup.open()

    def invalidRangePopup(self):
        self.popup = ErrorPopup()
        self.popup.open()

    def useInputs(self, g, ow, act, inact):
        """retrieves user inputs and adds new JLab to the database or overwrites existing jlab"""
        global privileges_strings
        c = []
        for i in self.children:
            for j in i.children[3].children:
                c.append(str(j.children[0].text))
        c.reverse()

        name = self.children[0].children[1].children[0].children[0].children[2].text
        if len(name) > 0:
            cur.execute("SELECT {} FROM owner WHERE owner_name = \"{}\"".format(privileges_strings["owner"], str(name)))
            x = cur.fetchall()
            c.insert(5, int(x[0][0]))
        else:
            c.insert(5, '')

        if act.state == 'down':
            c.append('active')
        elif inact.state == 'down':
            c.append('inactive')

        try:
            # this crashes if you dont have a jlab num written
            c[0] = int(c[0])
            try:
                # if no jlab exists with the given name, create it
                jlab_insert = "INSERT INTO jlabs VALUES({},".format(c[0])
                for val in c[1:]:
                    if len(str(val)) == 0:
                        jlab_insert += 'NULL,'
                    else:
                        jlab_insert += '\"{}\",'.format(str(val))
                # Remove extraneous comma and add end parenthesis
                jlab_insert = jlab_insert[:-1]
                jlab_insert += ")"
                cur.execute(jlab_insert)
                conn.commit()
                # TRACK HISTORY jlab c[0] was created

                self.popup = Popup()
                self.popup.title = "Success!"
                self.popup.content = Label(text="JLab {} added to the database.".format(c[0]),
                                           halign='center')
                self.popup.size = (250, 150)
                self.popup.size_hint = (None, None)
                self.popup.auto_dismiss = True
                self.popup.open()
                self.clearInputs(g, ow)
            except:
                # Ask user if they want to override jlab or not
                self.popup = InvalidJLabPopup()
                self.popup.open()
                # Update if user chooses "Yes" on InvalidJLabPopup
                self.popup.children[0].children[0].children[0].children[1].bind(
                    on_press=lambda x: self.update_j(c, g, ow))  # TRACK HISTORY jlab c was overwritten
        except (mysql.connector.errors.DatabaseError, ValueError) as e:
            self.popup = ErrorPopup()
            self.popup.title = "Invalid JLab #"
            self.popup.content = Label(text="Please enter an integer\nfor the JLab #.", halign='center')
            self.popup.open()
            self.popup.auto_dismiss = True

    def update_j(self, c, g, ow):
        jlab_update = "UPDATE jlabs SET "
        for i in range(1, len(c)):
            if isinstance(c[i], (int, long)):
                jlab_update += "{} = {},".format(self.j_switch(i), c[i])
            elif i == 4 or len(c[i]) == 0:
                jlab_update += "{} = {},".format(self.j_switch(i), 'NULL')
            else:
                jlab_update += "{} = \"{}\",".format(self.j_switch(i), str(c[i]))
        jlab_update = jlab_update[:-1]
        jlab_update += " WHERE jlab_number = {}".format(c[0])
        self.clearInputs(g, ow)

        try:
            cur.execute(jlab_update)
            conn.commit()

            self.popup = Popup()
            self.popup.title = "Success!"
            self.popup.content = Label(text="JLab {} overwritten\nin the database.".format(c[0]),
                                       halign='center')
            self.popup.size = (250, 150)
            self.popup.size_hint = (None, None)
            self.popup.auto_dismiss = True
            self.popup.open()

        except (mysql.connector.errors.DatabaseError, ValueError) as e:
            print e

    def j_switch(self, index):
        """
        makes a switch statement from JLabs table (minus jlab_number) to be used to identify
        which JLab field(s) have been changed...returns column name of changed field(s)
        :param arg: index (in both list and switch) of changed field
        :return: column name of changed field
        """
        j_columns = get_columns("jlabs")

        switch = {}
        for i in range(len(j_columns)):
            switch[i] = j_columns[i]

        return switch.get(index, "nothing")

    def clearInputs(self, g, ow):
        """
        clears text inputs
        :param g: boxlayout containing text inputs
        :return:
        """
        for i in g.children:
            i.children[0].text = ''
        for i in ow.children:
            i.text = ''

    def createLayout(self, box):
        """method to read through labels of a JLab and create text fields to fill in and create a new jlab
        :param: box: the current boy layout"""
        # Get JLab labels
        j_labels = get_columns("jlabs")
        del j_labels[5]
        for lab in j_labels:
            if lab in dbDict:
                j_labels[j_labels.index(lab)] = dbDict[lab]

        # Create Add JLab screen layout
        b = BoxLayout(orientation='horizontal')
        for i in range(len(j_labels) - 1):

            b.add_widget(Label(text=j_labels[i]))
            b.add_widget(TextInput(write_tab=False, multiline=False))
            box.add_widget(b)
            if i < len(j_labels) - 2:
                b = BoxLayout(orientation='horizontal')

    def popOwnerProgram(self):
        self.popup = OwnerPopup()
        self.popup.open()


class MachineScreen(Screen):
    """class for the screen which adds a machine """
    new_mach_info = []
    prev_sel_jlab = -1

    def set_to_none(self, grid):
        grid.deselect_all_nodes(grid)

    def addMachine(self, g, act, inact):
        # see which jlab is selected, if none, machine will be added to unattached list
        global privileges_strings
        sel_jlab = -1
        if len(report_jlabs) > 0:
            sel_jlab = report_jlabs[0]
        # save entered info to a list then clear inputs

        for i in g.children:
            try:
                if i.children[0].text != '':
                    self.new_mach_info.append(i.children[0].text)
                else:
                    self.new_mach_info.append('NULL')
            except AttributeError:
                name = i.children[0].children[0].children[0].text
                cur.execute("select owner_code from owner where owner_name = '{}'".format(name))
                o_code = cur.fetchone()[0]
                self.new_mach_info.append(o_code)

        self.new_mach_info.reverse()

        if act.state == 'down':
            self.new_mach_info.append('active')
        elif inact.state == 'down':
            self.new_mach_info.append('inactive')

        # get newest machine code number
        cur.execute('select {} from machine'.format(privileges_strings["machine"]))
        row = cur.fetchall()
        num_machines = len(row)

        cur.execute("select j_status from jlabs where jlab_number = {}".format(sel_jlab))
        isActive = str(cur.fetchone()[0])
        if isActive == 'active':
            # create the new machine in the database and then link it to a jlab in hardware
            try:
                mach_insert = "INSERT INTO machine VALUES({},".format(num_machines + 1)
                for i in range(len(self.new_mach_info)):
                    if self.new_mach_info[i] != 'NULL':
                        mach_insert += "\"{}\"".format(str(self.new_mach_info[i]))
                    else:
                        mach_insert += self.new_mach_info[i]
                    mach_insert += ","
                mach_insert = mach_insert[:-1]
                mach_insert += ")"

                success_pop_msg = "\"{}\" machine added\nto the database.".format(self.new_mach_info[0])

                cur.execute(mach_insert)

                if sel_jlab >= 0:
                    cur.execute(
                        "SELECT machine_code FROM machine WHERE machine_name = \"{}\"".format(
                            str(self.new_mach_info[0])))
                    row = cur.fetchone()
                    # Parse out machine_code
                    for code in row:
                        mach_code = int(code)
                    cur.execute("INSERT INTO hardware VALUES {}".format((sel_jlab, mach_code)))
                    success_pop_msg = success_pop_msg[:-1] + "\n and linked to JLab {}.".format(sel_jlab)
                conn.commit()
                # TRACK HISTORY machine self.new_mach_info[0] was created and added to sel_jlab

                self.popup = Popup()
                self.popup.title = "Success!"
                self.popup.content = Label(text=success_pop_msg, halign='center')
                self.popup.size = (300, 150)
                self.popup.size_hint = (None, None)
                self.popup.auto_dismiss = True
                self.popup.open()

                self.clearInputs(g)
                self.new_mach_info = []
            except mysql.connector.DatabaseError as e:
                self.popup = ErrorPopup()
                self.popup.size = (len(str(e)) * 8, 100)
                self.popup.content = Label(text=str(e))
                self.popup.auto_dismiss = True
                self.popup.open()
                self.new_mach_info = []
        else:
            self.popup = InactiveLink()
            self.popup.open()

    def clearInputs(self, g):
        grid = self.children[1].children[0].children[1].children[0].children[0]
        for i in g.children:
            try:
                i.children[0].children[0].children[0].text = ''
            except:
                i.children[0].text = ''
            self.children[1].children[0].children[1].children[2].children[0].children[1].text = ''
            #grid.deselect_all_nodes(grid)

    def createLayout(self, box):
        """method to read through labels of a machine and create text fields to fill in and create a new machine
        :param: box: the current boy layout"""
        # Get Machine labels
        m_labels = get_columns("machine")
        del m_labels[0]
        m_labels[2] = 'Company Contact'
        for lab in m_labels:
            if lab in dbDict:
                m_labels[m_labels.index(lab)] = dbDict[lab]

        # Create Machine screen layout
        b = BoxLayout(orientation='horizontal')
        for i in range(len(m_labels) - 1):
            b.add_widget(Label(text=m_labels[i]))
            if i == 2:
                owner_stuff = BoxLayout(orientation='horizontal')
                selectBTN = Button(size_hint=(.3, 1), text='Select')
                owner_stuff.add_widget(selectBTN)
                selectBTN.bind(on_release=partial(self.popOwnerProgram, owner_stuff))
                baby1 = BoxLayout(size_hint=(.2, 1), orientation='vertical')
                baby1.add_widget(Label(text='Name:'))
                owner_stuff.add_widget(baby1)
                ownerI = BoxLayout(size_hint=(.5, 1), orientation='vertical', id='ownerI')
                nameLabel = Label(text='')
                ownerI.add_widget(nameLabel)
                owner_stuff.add_widget(ownerI)
                b.add_widget(owner_stuff)
            else:
                b.add_widget(TextInput(write_tab=False, multiline=False))
            box.add_widget(b)
            if i < len(m_labels) - 2:
                b = BoxLayout(orientation='horizontal')

    def compOwner(self, btn):
        pass

    def popOwnerProgram(self, box, btn):
        self.popup = OwnerPopup2()
        self.popup.get_machine(box, True)
        self.popup.open()

    def ReadInput(self):
        """method allows users to type jlab number and lookup instead of scrolling through jlabs """
        SelectedJlab = (self.children[1].children[0].children[1].children[2].children[0].children[1].text)
        grid = self.children[1].children[0].children[1].children[0].children[0]
        abc = 0
        grid.deselect_all_nodes(grid)
        for a in self.children[1].children[0].children[1].children[0].children[0].children:
            if str(a.text) == str(SelectedJlab):
                grid.select_node(a)
                abc = 1
        if abc == 0:
            if SelectedJlab != '':
                self.popup = LookupErrorPopup()
                self.popup.open()


class LinkScreen(Screen):
    """ screen to link unattached machines to jlabs"""
    prev_sel_jlab = -1
    selected_mach = []

    # create a tooltip_link for this screen
    tooltip_link = Tooltip()
    # list of all text inputs that need tooltips
    tis_link = []

    # TOOLTIP METHODS
    def __init__(self, **kwargs):
        """
        init creates screen to be ready to track mouse movements
        :param kwargs:
        """
        Window.bind(mouse_pos=self.on_mouse_pos)
        super(Screen, self).__init__(**kwargs)

    def on_mouse_pos(self, *args):
        """
        tracks mouse position and shows tooltip when mouse is over the comment tab
        :param args:
        :return:
        """
        if not self.get_root_window():
            return
        pos = args[1]
        self.tooltip_link.pos = pos
        x = self.tooltip_link.pos[0] - self.tooltip_link.size[0]
        self.tooltip_link.pos = (x, self.tooltip_link.pos[1])
        Clock.unschedule(self.display_tooltip)  # cancel scheduled event since I moved the cursor
        self.close_tooltip()  # close if it's opened
        for i in self.tis_link:
            if Label(pos=i.to_window(*i.pos), size=i.size).collide_point(*self.to_widget(*pos)):
                self.tooltip_link.text = i.text
                Clock.schedule_once(self.display_tooltip, 1)

    def close_tooltip(self, *args):
        Window.remove_widget(self.tooltip_link)

    def display_tooltip(self, *args):
        Window.add_widget(self.tooltip_link)

    def on_checkbox_active(self, checkbox, value):
        # see which machines are selected to be added to a jlab
        if value:
            self.selected_mach.append(checkbox.id)
        else:
            self.selected_mach.remove(checkbox.id)

    def createLayout(self, box):
        """
        queries for unattached machines and displays them in a table
        :param box: where unattached machines will be listed
        :return: None
        """
        global privileges_strings
        box.clear_widgets()
        box.size_hint = (1, .9)
        box.orientation = 'vertical'

        self.selected_mach = []
        # Query Machine table to get table header names
        mLabels = get_columns("machine")
        # Remove machine_code field
        del mLabels[0]
        del mLabels[2]
        # write labels for unattached machines
        lab = BoxLayout(size_hint=(1, .1), padding=10, spacing=10)
        lab.add_widget(Label())
        for l in mLabels:
            if l in dbDict:
                lab.add_widget(Label(text=dbDict[l], halign='center'))
            else:
                lab.add_widget(Label(text=l, halign='center'))
        box.add_widget(lab)

        # query for unattached machines in DB
        cur.execute("SELECT {} FROM machine WHERE machine_code NOT IN(SELECT machine_code FROM hardware)".format(
            privileges_strings["machine"]))
        rows = cur.fetchall()
        machine_info = []

        # Convert to list of strings
        for row in rows:
            row = list(row)
            del row[0]
            for i in range(len(row)):
                row[i] = str(row[i])
            machine_info.append(row)

        # add all unattached machine info to table
        uMachs = BoxLayout(orientation='vertical', size_hint=(1, None), size=(100, len(rows) * 35))

        for m in machine_info:
            r = BoxLayout()
            checkbox = CheckBox(id=m[0])
            checkbox.bind(active=self.on_checkbox_active)
            r.add_widget(checkbox)
            for i in range(len(m)):
                if i == 2:
                    pass
                elif i == 7:
                    if m[i] == 'None':
                        ti = MyTextInput(text='', readonly=True, disabled=True, disabled_foreground_color=(0, 0, 0, 1))
                    else:
                        ti = MyTextInput(text=m[i], readonly=True, disabled=True, disabled_foreground_color=(0, 0, 0, 1))
                    self.tis_link.append(ti)
                    r.add_widget(ti)
                else:
                    if m[i] == 'None':
                        r.add_widget(TextInput(text='', readonly=True, disabled=True, disabled_foreground_color=(0, 0, 0, 1)))
                    else:
                        r.add_widget(TextInput(text=m[i], readonly=True, disabled=True, disabled_foreground_color=(0, 0, 0, 1)))
            uMachs.add_widget(r)
        sv = ScrollView(size_hint=(1, .9))
        sv.add_widget(uMachs)
        box.add_widget(sv)

    def linkMachine(self, box, grid):
        """
        called when button is pressed to link machines to a jlab
        :param box: layout where unattached machines are listed
        :param grid: selectable grid containing JLab numbers
        :return: None
        """
        global privileges_strings

        # if there is a jlab and a machine selected
        if len(report_jlabs) > 0 and len(self.selected_mach) > 0:
            sel_jlab = report_jlabs[0]
            # create link(s) in hardware table
            for mname in self.selected_mach:
                currM = get_m_code(mname)
                cur.execute("select {} from jlabs where jlab_number = {}".format(privileges_strings["jlabs"], sel_jlab))
                lab = cur.fetchone()
                if lab[-1] == 'inactive':
                    self.popup = InactiveLink()
                    self.popup.open()

                else:
                    cur.execute("INSERT INTO hardware VALUES({},{})".format(sel_jlab, currM))
                    conn.commit()
                    box.clear_widgets()
                    grid.deselect_all_nodes(grid)
                    self.createLayout(box)
            # TRACK HISTORY machine currM was linked to sel_jlab
        else:
            # if there is no jlab or machine selected, create warning popup
            self.popup = SelectJLabPopup()
            if len(report_jlabs) == 0:
                if len(self.selected_mach) == 0:
                    self.popup.title = "Please select the JLab and machine(s) to be linked."
                else:
                    self.popup.title = "Please select the JLab to be linked to the selected machine(s)."
            else:
                self.popup.title = "Please select the machine(s) to be linked to the selected JLab."
            self.popup.open()

    def clearInputs(self, grid, cbs):
        grid.deselect_all_nodes(grid)
        self.children[1].children[0].children[1].children[1].children[1].text = ''
        for r in cbs.children[0].children[0].children:
            r.children[8].active = False

    def ReadInput(self):
        """method allows users to type jlab number and lookup instead of scrolling through jlabs """
        SelectedJlab = (self.children[1].children[0].children[1].children[1].children[1].text)
        grid = self.children[1].children[0].children[1].children[0].children[0]
        abc = 0
        grid.deselect_all_nodes(grid)
        for a in self.children[1].children[0].children[1].children[0].children[0].children:
            if str(a.text) == str(SelectedJlab):
                grid.select_node(a)
                abc = 1
        if abc == 0:
            if SelectedJlab != '':
                self.popup = LookupErrorPopup()
                self.popup.open()


class HistoryScreen(Screen):
    prev_sel_j = 0
    past_user = ""

    # create a tooltip for this screen
    hist_tooltip = Tooltip()
    # list of all text inputs that need tooltips
    hist_tis = []
    # Create dictionary for plain-English version of History fields
    hDict = {"machine_code": "Machine Name", "user": "User", "changed": "Change Summary", "modified": "Date Modified",
             "prev_data": "FROM", "curr_data": "TO"}

    # TOOLTIP METHODS
    def __init__(self, **kwargs):
        """
        init creates screen to be ready to track mouse movements
        :param kwargs:
        """
        Window.bind(mouse_pos=self.on_mouse_pos)
        super(Screen, self).__init__(**kwargs)

    def on_mouse_pos(self, *args):
        """
        tracks mouse position and shows tooltip when mouse is over the comment tab
        :param args:
        :return:
        """
        if not self.get_root_window():
            return
        pos = args[1]
        self.hist_tooltip.pos = pos
        x = self.hist_tooltip.pos[0] - self.hist_tooltip.size[0]
        self.hist_tooltip.pos = (x, self.hist_tooltip.pos[1])
        Clock.unschedule(self.display_tooltip)  # cancel scheduled event since I moved the cursor
        self.close_tooltip()  # close if it's opened
        for i in self.hist_tis:
            if Label(pos=i.to_window(*i.pos), size=i.size).collide_point(*self.to_widget(*pos)):
                self.hist_tooltip.text = i.text
                Clock.schedule_once(self.display_tooltip, 1)

    def close_tooltip(self, *args):
        Window.remove_widget(self.hist_tooltip)

    def display_tooltip(self, *args):
        Window.add_widget(self.hist_tooltip)

    # END TOOLTIP METHODS

    def set_j_to_none(self, j_grid, u_grid):
        j_grid.deselect_all_nodes(j_grid)
        u_grid.deselect_all_nodes(u_grid)

    def get_num_changes(self, j_num, username):
        """gets the length of machine_info aka how many machines are in the jlab
        :return: length of list, int"""
        global privileges_strings

        # Now populate table with machines not listed on Hardware table (i.e. unattached machines)
        if j_num < 0:
            if len(username) > 0:
                cur.execute(
                    "SELECT {} FROM History WHERE jlab_number IS NULL AND user = \"{}\"".format(
                        privileges_strings["History"],
                        username))
                rows = cur.fetchall()
            else:
                cur.execute("SELECT {} FROM history WHERE jlab_number IS NULL".format(privileges_strings["History"]))
                rows = cur.fetchall()
        else:
            if len(username) > 0:
                cur.execute(
                    "SELECT {} FROM History WHERE jlab_number = {} AND user = \"{}\"".format(
                        privileges_strings["History"],
                        int(j_num), username))
                rows = cur.fetchall()
            else:
                cur.execute(
                    "SELECT {} FROM History WHERE jlab_number = {}".format(privileges_strings["History"], int(j_num)))
                rows = cur.fetchall()

        return len(rows)

    def create_history_table(self, jlab_n, hBox, hLb, j_grid, username):
        """method to create the table holding info for all of the machines in the current jlab
        This defaults to no jlab being selected, and thus it displays unattached machines """
        # Only refresh screen if NEW JLab is selected

        if jlab_n != self.prev_sel_j or username != self.past_user:
            # Update previously selected JLab and user
            self.prev_sel_j = jlab_n
            self.past_user = username

            hBox.clear_widgets()
            hLb.clear_widgets()

            #
            hist_labels = get_columns("History")

            hist_fields = []
            for label in hist_labels:
                if label in self.hDict:
                    hist_fields.append(label)

            fields = ""
            for field in hist_fields:
                fields += field + ","

            fields = fields[:-1]

            # Remove h_code, jlab_number field
            del hist_labels[0]
            del hist_labels[0]

            for lab in hist_labels:
                if lab in self.hDict:
                    if lab == "user":
                        hLb.add_widget(Label(text=self.hDict[lab], halign='center', size_hint_x=None, width=100))
                    elif lab == "modified":
                        hLb.add_widget(Label(text=self.hDict[lab], halign='center', size_hint_x=None, width=150))
                    elif lab == "machine_code":
                        hLb.add_widget(Label(text=self.hDict[lab], halign='center', size_hint_x=None, width=200))
                    else:
                        hLb.add_widget(Label(text=self.hDict[lab], halign='center'))
                else:
                    hLb.add_widget(Label(text=lab, halign='center'))

            hist_table = []

            if jlab_n < 0:
                # Deselect nodes so currently selected JLab defaults back to -1
                j_grid.deselect_all_nodes(j_grid)
                #
                if len(username) > 0:
                    cur.execute(
                        "SELECT {} FROM history WHERE jlab_number IS NULL AND user = \"{}\"".format(fields, username))
                    rows = cur.fetchall()
                else:
                    cur.execute("SELECT {} FROM history WHERE jlab_number IS NULL".format(fields))
                    rows = cur.fetchall()
            else:
                #
                if jlab_n is None:
                    pass
                elif len(username) > 0:
                    cur.execute(
                        "SELECT {} FROM history WHERE jlab_number = {} AND user = \"{}\"".format(fields, int(jlab_n),
                                                                                                 username))
                    rows = cur.fetchall()
                else:
                    cur.execute("SELECT {} FROM history WHERE jlab_number = {}".format(fields, int(jlab_n)))
                    rows = cur.fetchall()

            hBox.size = (400, len(rows) * 35)

            # Convert to list of strings
            for row in rows:
                row = list(row)
                for i in range(len(row)):
                    row[i] = str(row[i])
                hist_table.append(row)

            # Replace machine_code with machine_name
            for i in range(len(hist_table)):
                if hist_table[i][0] != 'None':
                    try:
                        cur.execute(
                            "SELECT machine_name FROM machine WHERE machine_code = {}".format(int(hist_table[i][0])))
                        row = cur.fetchone()
                        for code in row:
                            hist_table[i][0] = str(code)
                    except TypeError:
                        pass

            # Have to recreate hBoxC in hBox
            hC = BoxLayout(orientation='horizontal', size_hint_y=None, height=35)
            # Add new widgets
            hBox.add_widget(hC)

            # if self.get_num_changes(jlab_n, username) > 0:
            for i in range(len(hist_table)):
                hC = BoxLayout(orientation='horizontal', size_hint_y=None, height=35)
                for j in range(len(hist_table[i])):
                    if j == 0:
                        if hist_table[i][j] == 'None':
                            hC.add_widget(TextInput(size_hint_x=None, text='', readonly=True, disabled=True,
                                                    disabled_foreground_color=(0, 0, 0, 1), width=200))
                        else:
                            hC.add_widget(TextInput(size_hint_x=None, text=hist_table[i][j], readonly=True, disabled=True,
                                                    disabled_foreground_color=(0, 0, 0, 1), width=200))
                    elif j == 1:
                        hC.add_widget(TextInput(size_hint_x=None, text=hist_table[i][j], readonly=True, disabled=True,
                                                disabled_foreground_color=(0, 0, 0, 1), width=100))
                    elif j == 2 or j == 3 or j == 4:
                        # these will be boxes which use tooltips
                        if hist_table[i][j] == 'None':
                            h_ti = MyTextInput(text='', readonly=True, disabled=True, disabled_foreground_color=(0, 0, 0, 1))
                        else:
                            h_ti = MyTextInput(text=hist_table[i][j], readonly=True, disabled=True,
                                               disabled_foreground_color=(0, 0, 0, 1))
                        self.hist_tis.append(h_ti)
                        hC.add_widget(h_ti)
                    elif j == 5:
                        hC.add_widget(TextInput(size_hint_x=None, text=hist_table[i][j], readonly=True, disabled=True,
                                                disabled_foreground_color=(0, 0, 0, 1), width=150))
                    else:
                        if hist_table[i][j] == 'None':
                            hC.add_widget(TextInput(text='', readonly=True, disabled=True, disabled_foreground_color=(0, 0, 0, 1)))
                        else:
                            hC.add_widget(TextInput(text=hist_table[i][j], readonly=True, disabled=True,
                                                    disabled_foreground_color=(0, 0, 0, 1)))
                if i < len(hist_table):
                    hBox.add_widget(hC)


# ##################################################    END SCREENS     ################################################
class TestApp(App):

    def build(self):
        self.title = 'JLab Inventory Manager'
        # Bind custom on_request_close method (popup prompt on close attempt)
        Window.bind(on_request_close=self.on_request_close)
        # Populate the screen manager with login screen only,
        # Successful login will remove the login screen and populate with the other screens.
        sm.add_widget(LoginScreen(name='login'))
        sm.current = 'login'
        return sm

    def on_request_close(self, *args):
        self.popQuitProgram()
        return True

    def popQuitProgram(self):
        popup = QuitPopup()
        popup.open()


if __name__ == '__main__':
    TestApp().run()