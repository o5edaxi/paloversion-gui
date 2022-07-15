#! /usr/bin/env python3

import os
import subprocess
import sys
import time
import re
import csv
import shutil
import logging

from kivy.uix.dropdown import DropDown
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.app import App
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.screenmanager import ScreenManager, Screen


# Customize these if necessary
########################
FIRMWARE_PATH = "/media/usb0/"
NETWORK_INTERFACE = "eth0"
SCRIPT_PATH = "/home/pi/Desktop/paloversion.sh"
SCRIPT_ROOT = "/home/pi/Desktop/"
CSV_DELIM = ","
########################

TEXT1 = """Remove power to shutdown or restart the Raspberry at any time.

1. Place the firmware files and the up to date .csv in the usb drive
2. Place Threat and AV files in the usb drive keeping their original filename
3. Paste the Panorama Authkey in a file named "authkey.txt" and put in the usb drive
4. Connect the Raspberry to the firewall, or multiple firewalls using a switch
5. Make sure the password is admin/admin or admin/Admin123
6. Select the desired version and press START
7. The jobs are yellow when in progress, red when failed, and green when completed
8. Tap on the serial number of a firewall to view the detailed upgrade logs

New features are enabled with paloversion v1.4.0 or newer."""

FEATURES_CHECKS = {'errors': '-i',
                   'licenses': '-k',
                   'content': '-t "test" -a "test"',
                   'configuration': '-c',
                   'authkey': '-p "test"'}
DESIRED_VERSION = "Pan-OS Selection"
Window.fullscreen = 'auto'
Window.show_cursor = False
OPTIONS = []
yellow = [1, 1, 0, 1]
green = [0, 1, 0, 1]
red = [1, 0, 0, 1]

chosenserial = ""
status_array = []

regexcsv = re.compile(r'^\w+\.csv$')
regexver = re.compile(r'^[0-9.a-zA-Z-]+$')
regexlogs = re.compile(r'^(PaloVersionBatch|\d+|fe80[\w:]+)\.log$')
regexcontent = re.compile(r'panupv2-all-contents-\d+-\d+')
regexantivirus = re.compile(r'panup-all-antivirus-\d+-\d+')

logging.basicConfig(filename="/home/pi/app.logs", filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S', level=logging.INFO)


def monitor_files(path):
    matches = []
    for root, _, files in os.walk(path):
        for file in files:
            if re.match(regexlogs, file) and file != "PaloVersionBatch.log":
                try:
                    with open(os.path.join(root, file), 'r') as f:
                        contents = f.read()
                        if contents != "":
                            active_serial = [file, yellow]
                            if "---FAILED---" in contents:
                                active_serial[1] = red
                            elif "---FINISHED---" in contents:
                                active_serial[1] = green
                            matches.append(active_serial)
                except Exception:
                    active_serial = [file, red]
                    matches.append(active_serial)
    return matches


def tail_file(serial):
    file_contents = ""
    try:
        if serial != "":
            with open(os.path.join(SCRIPT_ROOT, serial), 'r') as f:
                file_contents = f.read()
    except Exception as e:
        if serial == "PaloVersionBatch.log":
            logging.error('Error reading log file for serial {} with exception {}.\nCheck that '
                          'firewalls are reachable and MAC address is in filter.\n'
                          'Ensure the number of hosts is less than BATCH_MAX'
                          ' in paloversion.sh'.format(serial, e))
            file_contents = ('Error reading log file for serial {} with exception {}.\nCheck that '
                             'firewalls are reachable and MAC address is in filter.\n'
                             'Ensure the number of hosts is less than BATCH_MAX'
                             ' in paloversion.sh'.format(serial, e))
        else:
            logging.error('Error reading log file for serial {} with exception {}'.format(serial,
                                                                                          e))
            file_contents = 'Error reading log file for serial {} with exception {}'.format(serial,
                                                                                            e)
    return file_contents


def get_versions(path):
    matches = []
    for root, _, files in os.walk(path):
        for file in files:
            if re.match(regexcsv, file):
                try:
                    shutil.copyfile(os.path.join(root, file), os.path.join(SCRIPT_ROOT, file))
                except Exception as e:
                    logging.error("Failed to copy file {} from usb key, {}".format(file, e))
                try:
                    if file == "content.csv":
                        continue
                    with open(os.path.join(root, file), 'r') as f:
                        csvobj = csv.reader(f, delimiter=CSV_DELIM)
                        rows = list(csvobj)
                        for row in rows:
                            if row[1] not in matches and re.match(regexver, row[1]):
                                matches.append(row[1])
                except Exception as e:
                    logging.error("Error opening file {}{}, {}".format(root, file, e))
    matches.sort(reverse=True)
    return matches


def cleanup(path):
    for root, _, files in os.walk(path):
        for file in files:
            if re.match(regexlogs, file):
                try:
                    os.remove(os.path.join(root, file))
                except Exception:
                    logging.error("Failed to remove old log {}".format(file))
                    pass


def find_authkey(path):
    for root, _, files in os.walk(path):
        for file in files:
            if file == "authkey.txt":
                try:
                    with open(os.path.join(root, file), 'r') as f:
                        return f.readline().rstrip('\n')
                except Exception:
                    pass
    return ""


def find_content(path):
    for root, _, files in os.walk(path):
        for file in files:
            if re.match(regexcontent, file):
                return file
    return ""


def find_antivirus(path):
    for root, _, files in os.walk(path):
        for file in files:
            if re.match(regexantivirus, file):
                return file
    return ""


def check_features(option):
    # Test new paloversion options
    try:
        subprocess.check_output([SCRIPT_PATH, option, '-h'])
        return False
    except subprocess.CalledProcessError:
        return True


class Panel1(Screen):
    def __init__(self, **kwargs):
        super(Panel1, self).__init__(**kwargs)
        box = BoxLayout(orientation='vertical')
        label = Label(text=TEXT1, font_size=12)
        button = Button(text=DESIRED_VERSION, font_size=30, size_hint_y=0.35,
                        on_release=self.list)

        mac_button = ToggleButton(text='Exclude non-PA\nMAC addresses', font_size=15,
                                  halign='center', state='down')
        dry_button = ToggleButton(text="Dry Run", font_size=15)
        shutdown_button = ToggleButton(text="Shutdown\nafter upgrading", font_size=15,
                                       halign='center')
        ignore_errors_button = ToggleButton(text="Don't halt\non errors", font_size=15,
                                            halign='center',
                                            disabled=check_features(FEATURES_CHECKS['errors']))
        license_button = ToggleButton(text="Install\nlicenses", font_size=15, halign='center',
                                      disabled=check_features(FEATURES_CHECKS['licenses']))
        content_button = ToggleButton(text="Content\n& AV", font_size=15, halign='center',
                                      disabled=check_features(FEATURES_CHECKS['content']))
        config_button = ToggleButton(text="Config", font_size=15, halign='center',
                                     disabled=check_features(FEATURES_CHECKS['configuration']))
        authkey_button = ToggleButton(text="Panorama\nAuthkey", font_size=15, halign='center',
                                      disabled=check_features(FEATURES_CHECKS['authkey']))
        box.add_widget(label)
        box.add_widget(button)

        boxlayout1 = BoxLayout(size_hint_y=0.35)
        boxlayout1.add_widget(mac_button)
        boxlayout1.add_widget(dry_button)
        boxlayout1.add_widget(shutdown_button)
        boxlayout1.add_widget(ignore_errors_button)
        box.add_widget(boxlayout1)

        boxlayout2 = BoxLayout(size_hint_y=0.35)
        boxlayout2.add_widget(license_button)
        boxlayout2.add_widget(content_button)
        boxlayout2.add_widget(config_button)
        boxlayout2.add_widget(authkey_button)
        box.add_widget(boxlayout2)

        enterbutton = Button(text='START', font_size=30, size_hint_y=0.35, on_release=self.close)
        box.add_widget(enterbutton)
        self.add_widget(box)

    def list(self, button):
        self.parent.current = 'Version'

    def close(self, bar):
        if DESIRED_VERSION != "Pan-OS Selection":
            OPT_ARGS = ""
            if self.children[0].children[2].children[3].state != "down":
                # MAC
                OPT_ARGS += '-m '
            if self.children[0].children[2].children[2].state == "down":
                # DRY
                OPT_ARGS += '-d '
            if self.children[0].children[2].children[1].state == "down":
                # SHUTDOWN
                OPT_ARGS += '-s '
            if self.children[0].children[2].children[0].state == "down":
                # ERRORS
                OPT_ARGS += '-i '
            if self.children[0].children[1].children[3].state == "down":
                # LICENSE
                OPT_ARGS += '-k '
            if self.children[0].children[1].children[2].state == "down":
                # CONTENT
                content_path = find_content(FIRMWARE_PATH)
                if content_path == "":
                    self.parent.current = 'ContentError'
                    return
                antivirus_path = find_antivirus(FIRMWARE_PATH)
                if antivirus_path == "":
                    self.parent.current = 'AntivirusError'
                    return
                OPT_ARGS += '-t "{}" -a "{}" '.format(content_path, antivirus_path)
            if self.children[0].children[1].children[1].state == "down":
                # CONFIG
                OPT_ARGS += "-c "
            if self.children[0].children[1].children[0].state == "down":
                # AUTHKEY
                authkey = find_authkey(FIRMWARE_PATH)
                if authkey == "":
                    self.parent.current = 'AuthkeyError'
                    return
                OPT_ARGS += '-p "{}"'.format(authkey)

            command = '{} -f {} -z "" "" "" "{}" "{}" "{}"'.format(SCRIPT_PATH, OPT_ARGS,
                                                                   FIRMWARE_PATH,
                                                                   DESIRED_VERSION,
                                                                   NETWORK_INTERFACE)
            print(command)
            subprocess.Popen(command, shell=True, stdin=None, stdout=open(os.devnull, 'wb'),
                             stderr=open(os.devnull, 'wb'), cwd=SCRIPT_ROOT)
            time.sleep(1)
            self.parent.current = 'General'

    def on_pre_enter(self):
        self.children[0].children[3].text=DESIRED_VERSION


class Panel2(Screen):
    def __init__(self, **kwargs):
        global status_array
        super(Panel2, self).__init__(**kwargs)
        Clock.schedule_interval(self.refresher, 10)
        box = GridLayout(cols=1, row_force_default=True, row_default_height=40, spacing=[1, 1],
                         size_hint=(1, None), padding=[0, 0, 100, 0])
        box.bind(minimum_height=box.setter('height'))
        button = Button(text="Tap a serial number to view the detailed upgrade logs", font_size=25,
                        background_normal="", background_color=yellow, color=[0, 0, 0, 1])
        box.add_widget(button)
        button = Button(text="PaloVersionBatch.log", font_size=30, background_normal="",
                        background_color=yellow, color=[0, 0, 0, 1], on_release=self.drilldown)
        box.add_widget(button)
        status_array = monitor_files(SCRIPT_ROOT)
        for serial in status_array:
            button = Button(text=str(serial[0]), font_size=30, background_normal="",
                            background_color=serial[1], color=[0, 0, 0, 1],
                            on_release=self.drilldown)
            box.add_widget(button)
        root = ScrollView(size_hint=(1, None), size=(Window.width, Window.height),
                          scroll_type=['content'])
        root.add_widget(box)
        self.add_widget(root)

    def refresher(self, bar):
        global status_array
        status_array = monitor_files(SCRIPT_ROOT)
        self.children[0].children[0].clear_widgets()
        button = Button(text="Tap a serial number to view the detailed upgrade logs", font_size=25,
                        background_normal="", background_color=yellow, color=[0, 0, 0, 1])
        self.children[0].children[0].add_widget(button)
        if red in [item[1] for item in status_array]:
            maincolor = red
            maintext = "Upgrades finished with errors"
        elif yellow in [item[1] for item in status_array]:
            maincolor = yellow
        elif status_array == []:
            maincolor = yellow
        else:
            maincolor = green
            maintext = "Upgrades finished without errors"
        button = Button(text="PaloVersionBatch.log", font_size=30, background_normal="",
                        background_color=maincolor, color=[0, 0, 0, 1], on_release=self.drilldown)
        self.children[0].children[0].add_widget(button)
        if maincolor != yellow:
            self.children[0].children[0].add_widget(Button(text=maintext, font_size=25,
                                                           background_normal="",
                                                           background_color=maincolor,
                                                           color=[0, 0, 0, 1]))
        for serial in status_array:
            button = Button(text=str(serial[0]), font_size=30, background_normal="",
                            background_color=serial[1], color=[0, 0, 0, 1],
                            on_release=self.drilldown)
            self.children[0].children[0].add_widget(button)

    def drilldown(self, button):
        global chosenserial
        chosenserial = button.text
        self.parent.current = 'Details'


class Panel3(Screen):
    def __init__(self, **kwargs):
        super(Panel3, self).__init__(**kwargs)
        Clock.schedule_interval(self.refresher, 5)
        label = Label(text=tail_file(chosenserial), size_hint=(None, None))
        label.bind(texture_size=lambda *x: (label.setter('height')(label, label.texture_size[1]),
                                            label.setter('width')(label, label.texture_size[0])))
        scroll = ScrollView(size_hint=(None, None), size=(Window.width, Window.height),
                            pos_hint={'top': 1, 'right': 1})
        scroll.add_widget(label)
        btn = Button(text='Back', font_size=30, background_normal="", background_color=red,
                     color=[0, 0, 0, 1], on_release=self.close, size_hint=(None, None),
                     size=(75, 50), pos_hint={'top': 1, 'right': 1})
        grid = RelativeLayout()
        grid.add_widget(scroll)
        grid.add_widget(btn)
        self.add_widget(grid)

    def refresher(self, bar):
        self.children[0].children[1].children[0].text = tail_file(chosenserial)

    def close(self, bar):
        global chosenserial
        chosenserial = ""
        self.parent.current = 'General'

    def on_pre_enter(self):
        self.refresher(self)


class Panel4(Screen):
    def __init__(self, **kwargs):
        super(Panel4, self).__init__(**kwargs)
        scroll = ScrollView(size_hint=(1, None), size=(Window.width, Window.height),
                            scroll_type=['content'])
        box = GridLayout(cols=1, row_default_height=40, spacing=[1, 1],
                         size_hint=(1, None), padding=[0, 0, 100, 0])
        box.bind(minimum_height=box.setter('height'))
        for option in OPTIONS:
            btn = Button(text=option, size_hint_y=None, height=44)
            btn.text = option
            btn.bind(on_release=lambda btn: self.close(btn.text))
            box.add_widget(btn)
        scroll.add_widget(box)
        anchor = AnchorLayout(anchor_x='right')
        helptext = Label(text="[color=ffffff]Scroll[/color]", size_hint_x=None, markup=True)
        anchor.add_widget(helptext)
        anchor.add_widget(scroll)
        self.add_widget(anchor)

    def close(self, text):
        global DESIRED_VERSION
        DESIRED_VERSION = text
        self.parent.current = 'Intro'


class Panel5(Screen):
    def __init__(self, **kwargs):
        super(Panel5, self).__init__(**kwargs)
        anchor = AnchorLayout()
        anchor.add_widget(Label(text='Content file not found.\nContent file name must be in format'
                                '\n"panupv2-all-contents-1234-1234"', font_size=40))
        self.add_widget(anchor)


class Panel6(Screen):
    def __init__(self, **kwargs):
        super(Panel6, self).__init__(**kwargs)
        anchor = AnchorLayout()
        anchor.add_widget(Label(text='Antivirus file not found.\nAntivirus file name must be in '
                                'format\n"panup-all-antivirus-1234-1234"', font_size=40))
        self.add_widget(anchor)


class Panel7(Screen):
    def __init__(self, **kwargs):
        super(Panel7, self).__init__(**kwargs)
        anchor = AnchorLayout()
        anchor.add_widget(Label(text='Panorama authkey not found.\nAuthkey must be contained\nin '
                                'file named "authkey.txt"', font_size=40))
        self.add_widget(anchor)


class Manager(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(Panel1(name='Intro'))
        sm.add_widget(Panel2(name='General'))
        sm.add_widget(Panel3(name='Details'))
        sm.add_widget(Panel4(name='Version'))
        sm.add_widget(Panel5(name='ContentError'))
        sm.add_widget(Panel6(name='AntivirusError'))
        sm.add_widget(Panel7(name='AuthkeyError'))
        return sm


class PanelError(App):
    def build(self):
        anchor = AnchorLayout()
        anchor.add_widget(Label(text="USB not inserted. Please insert and restart.", font_size=40))
        return anchor


time_start = time.time()

while True:
    try:
        if len(os.listdir(FIRMWARE_PATH)) != 0:
            break
    except Exception:
        logging.critical('USB not inserted')
        PanelError().run()
        sys.exit(1)
    if time.time() - time_start > 10:
        logging.critical('USB not inserted')
        PanelError().run()
        sys.exit(1)

cleanup(SCRIPT_ROOT)
OPTIONS = get_versions(FIRMWARE_PATH)

Manager().run()
