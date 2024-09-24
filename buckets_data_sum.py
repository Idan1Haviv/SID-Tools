# This file is (c) 2024 Securing SAM Ltd.
#
# It may not be reproduced, used, sold or transferred to any third party
# without the prior written consent of Securing SAM Ltd. All rights reserved.

"""
This script is used to filter and convert send bucket logs to json format.

Usage:
    Note: Please put the log file in this directory!!!
    python convert_send_bucket_logs.py -lfp <path_to_flow_logs_file> -cfp <path_to_classification_file>

Options:
    -lfp, --log_file_path <path_to_send_bucket_log_file>  Path to flow logs file
    -cfp, --classification_file_path <path_to_classification_file>  Path to classification file

!!! NOTE:
    This script assumes that flow logs file is in a specific format.
    Its important to run the following commands outside fo the container
    To collect the flow buckets run this commands in agent:
    cd /data/lxc/fsam/rootfs/crsp/log
    tail -F flow.log flow.log.1 | tee /mnt/sda1/flow.logs
"""

from abc import ABC, abstractmethod
from argparse import ArgumentParser
from functools import lru_cache
from json import dumps, load, loads
from logging import DEBUG, WARNING, StreamHandler, basicConfig, getLogger
from math import floor, log2
from typing import Any

import plotext as plt
from colorlog import ColoredFormatter
from ops_api import sam_config
from prettytable import PrettyTable
from requests import request

# Set the default log format and level
log_format = "%(log_color)s%(asctime)s|%(levelname)s|%(name)s|%(module)s.%(funcName)s:%(lineno)d|%(message)s"
log_level = DEBUG

# Set what color for each level
colors = {'DEBUG': 'green',
          'INFO': 'green',
          'WARNING': 'bold_yellow',
          'ERROR': 'bold_red',
          'CRITICAL': 'bold_purple'}

# Using colorlog library to set different colors for each log level
formatter = ColoredFormatter(log_format, log_colors=colors)
stream = StreamHandler()
stream.setLevel(log_level)
stream.setFormatter(formatter)

# Set the basic config for logging library
basicConfig(level=log_level, format=log_format, datefmt="%T", handlers=[stream])

getLogger("botocore").setLevel(WARNING)
getLogger("urllib3").setLevel(WARNING)

logger = getLogger(__name__)

agent_categories = [
    "general",
    "adult content",
    "alcohol tobacco and narcotics",
    "electronic commerce",
    "gambling",
    "religious associations",
    "social networking",
    "violence",
    "weapons",
    "social media",
    "media streaming",
    "gaming content",
    "advertisements"
]


def get_file_content() -> list[str]:
    with open(log_file_path, 'r') as f:
        content = f.readlines()
    return content


def format_bytes(size_in_bytes: int) -> str:
    # Convert bytes to MB or GB depending on size
    if size_in_bytes >= 1024 ** 3:  # 1 GB = 1024^3 bytes
        size_in_gb = size_in_bytes / (1024 ** 3)
        return f"{size_in_gb:.2f} GB"

    if size_in_bytes >= 1024 ** 2:  # 1 MB = 1024^2 bytes
        size_in_mb = size_in_bytes / (1024 ** 2)
        return f"{size_in_mb:.2f} MB"

    if size_in_bytes >= 1024:  # 1 KB = 1024 bytes
        size_in_kb = size_in_bytes / 1024
        return f"{size_in_kb:.2f} KB"

    return f"{size_in_bytes} bytes"


@lru_cache(maxsize=1)
def get_classification_defs() -> dict[str, list[dict[str, Any]]]:
    conf = sam_config.SamConfig('sam', 'staging')
    registration_url: str = conf.get_param("registration_domain")
    registration_token: str = conf.get_param("registration_token")

    url = f"https://{registration_url}/download/json_files/classification_defs/0"

    headers = {
        'Authorization': f'Token {registration_token}',
        'Cookie': 'Path=/'
    }

    response = request("GET", url, headers=headers, data={})
    return response.json()


@lru_cache(maxsize=1)
def get_classification_defs_local():
    with open("classification_defs_ext.json", 'r') as f:
        return load(f)


@lru_cache(maxsize=1)
def category_to_bitmap(categories: str | list[str]) -> int:
    """
    converts categories to bitmap
    :param categories: str | list[str] categories
    :return: int - category/s bitmap
    """
    if isinstance(categories, str):
        return 1 << agent_categories.index(categories)
    elif isinstance(categories, list):
        category_bitmap = 0
        for category in categories:
            category_bitmap += 1 << agent_categories.index(category)
        return category_bitmap
    else:
        raise TypeError("Supported types are str for a single category, or list for multiple categories")


@lru_cache(maxsize=1)
def bitmap_to_categories(bitmap) -> list[str]:
    """
    converts a bitmap to a list of categories
    :param bitmap: category index
    :return: list[str] - list of categories
    """
    categories = []
    while not log2(bitmap).is_integer():
        closest_bitmap_category = int(floor(log2(bitmap)))
        bitmap -= (2 ** closest_bitmap_category)
        categories.append(agent_categories[closest_bitmap_category])

    categories.append(agent_categories[int(log2(bitmap))])
    return categories


class AbstractClass(ABC):

    def __init__(self, index: int):
        self._index = index
        self._display_name: list[str] | str = NotImplemented
        self._tx: int = 0
        self._rx: int = 0
        self.usage_minutes: int = 0
        self.update_display_name()

    @abstractmethod
    def update_display_name(self) -> list[str] | str:
        pass

    @property
    def index(self):
        return self._index

    @index.setter
    def index(self, value):
        self._index = value

    @property
    def tx(self):
        return self._tx

    @tx.setter
    def tx(self, value):
        self._tx = value if not self._tx else self._tx + value

    @property
    def rx(self):
        return self._rx

    @rx.setter
    def rx(self, value):
        self._rx = value if not self._rx else self._rx + value


class Service(AbstractClass):

    def __init__(self, index):
        super(Service, self).__init__(index)

    def update_display_name(self) -> None:
        classification_defs: dict[str, list[dict[str, Any]]] = get_classification_defs_local() \
            if classification_file_path else get_classification_defs()
        for service in classification_defs['services']:
            if service['id'] == self._index:
                self._display_name = service['display_name']
                break
        else:
            self._display_name = f"Unknown service {self._index}"


class Category(AbstractClass):

    def __init__(self, index):
        super(Category, self).__init__(index)

    def update_display_name(self) -> None:
        self._display_name = bitmap_to_categories(self._index)


class Device:

    def __init__(self, ip: str):
        self.ip: str = ip
        self.services: list[Service] = []
        self.categories: list[Category] = []

    def __dict__(self):
        return {
            'ip': self.ip,
            'services': [service.__dict__ for service in self.services],
            'categories': [category.__dict__ for category in self.categories]
        }

    def get_service(self, index) -> Service | None:
        for service in self.services:
            if service.index == index:
                return service
        return None

    def get_category(self, index) -> Category | None:
        for category in self.categories:
            if category.index == index:
                return category
        return None

    def process_services(self, data: dict[str, dict[str, int]]) -> None:
        """
        Process services data and update the device services

        Example for data:
        {
            "14":
            {
                "rx": 92236,
                "tx": 106266
            },
            "21":
            {
                "rx": 105012,
                "tx": 10196
            },
            "23":
            {
                "rx": 55138,
                "tx": 30230
            }
        }

        :param data: dict of device services usage
        :return: None
        """
        for service_index, usage in data.items():

            service: Service | None = self.get_service(int(service_index))
            if not service:
                service = Service(int(service_index))
                self.services.append(service)

            service.rx = usage['rx']
            service.tx = usage['tx']
            service.usage_minutes += 1

    def process_categories(self, data: dict[str, dict[str, int]]) -> None:
        """
        Process categories data and update the device categories

        Example for data:
        {
            "1":
            {
                "rx": 92236,
                "tx": 106266
            }
        }

        :param data: dict of device categories usage
        :return: None
        """
        for category_index, usage in data.items():

            category: Category | None = self.get_category(int(category_index))
            if not category:
                category = Category(int(category_index))
                self.categories.append(category)

            category.rx = usage['rx']
            category.tx = usage['tx']
            category.usage_minutes += 1


class DevicesData:

    def __init__(self):
        self.devices: list[Device] = []

    def __dict__(self):
        returned_dict = {}
        for device in self.devices:
            returned_dict[device.ip] = device.__dict__()
        return returned_dict

    def get_device(self, ip):
        for device in self.devices:
            if device.ip == ip:
                return device
        return None


def content_filter(content: list[str]) -> list[dict]:
    """
    Filter send bucket logs and return only the json content
    Example for send bucket log:
    [276] 16/09/24 08:19:31 ../../src/cyber/flow/flow.c:1800:combine_and_send() <debug>   service id to send:
    {
        "ref_ts":1726489171,
        "bucket_size":60,
        "buckets":
        {
            "0":
            {
                "devices":
                {
                    "192.168.1.185":
                    {
                        "services":
                        {
                            "215":{"rx":208,"tx":356},
                            "91":{"rx":140008,"tx":345765},
                            "90":{"rx":165068,"tx":80297},
                            "104":{"rx":1356,"tx":1240},
                            "208":{"rx":50245,"tx":4817},
                            "23":{"rx":52,"tx":58},
                            "165":{"rx":40,"tx":0},
                            "45":{"rx":26050,"tx":8307},
                            "172":{"rx":7089,"tx":4178}
                        },
                        "categories":
                        {
                            "1":{"rx":440238,"tx":549737}
                        }
                    }
                }
            }
        }
    }
    :param content: buckets content
    :return: list of buckets dictionary
    """

    # split each line and get the last element which is json content
    # then parse it to dict using json.loads() function
    return [loads(line.split(' ')[-1]) for line in content]


def bucket_filter(devices_data: DevicesData, bucket: dict) -> None:
    """
    Filter and update device data
    Example for bucket:
        {
        "ref_ts": 1726489231,
        "bucket_size": 60,
        "buckets":
        {
            "0":
            {
                "devices":
                {
                    "192.168.1.159":
                    {
                        "categories":
                        {
                            "1":
                            {
                                "rx": 1843,
                                "tx": 554
                            }
                        }
                    },
                    "192.168.1.166":
                    {
                        "services":
                        {
                            "37":
                            {
                                "rx": 1459,
                                "tx": 1956
                            }
                        }
                    },
                    "192.168.1.182":
                    {
                        "categories":
                        {
                            "1":
                            {
                                "rx": 6192,
                                "tx": 6788
                            }
                        }
                    },
                    "10.20.0.10":
                    {
                        "categories":
                        {
                            "1":
                            {
                                "rx": 885,
                                "tx": 1879
                            }
                        }
                    }
                }
            }
        }
    },
    :param devices_data: dictionary of devices and their usage data
    :param bucket: new bucket to update device data
    :return: None
    """
    devices = bucket.get('buckets', {}).get("0", {}).get("devices", {})
    logger.info(f"{devices= }")

    if not devices:
        return

    for ip, data in devices.items():

        logger.info(f"{ip= }\n{data=}\n")

        device = devices_data.get_device(ip)
        if not device:
            device = Device(ip)
            devices_data.devices.append(device)

        if data.get('services'):
            device.process_services(data['services'])

        if data.get('categories'):
            device.process_categories(data['categories'])


def print_services(device: Device) -> None:
    table = PrettyTable()
    table.align = 'l'
    table.field_names = ['ID', 'Display Name', 'TX', 'RX', 'usage_minutes']
    for service in device.services:
        row = list(service.__dict__.values())
        row[2] = format_bytes(row[2])
        row[3] = format_bytes(row[3])
        table.add_row(row)
    table.sortby = 'ID'
    logger.info(f"\n{table}")

    services = list(map(lambda x: x._display_name, device.services))
    services_rx = list(map(lambda x: x._rx, device.services))
    services_tx = list(map(lambda x: x._tx, device.services))
    plt.simple_stacked_bar(services, [services_rx, services_tx], width=100, labels=['rx', 'tx'],
                           title=f'Services - {device.ip}')
    plt.show()


def print_categories(device: Device) -> None:
    # print categories
    table = PrettyTable()
    table.align = 'l'
    table.field_names = ['ID', 'Display Name', 'TX', 'RX', 'usage_minutes']
    for category in device.categories:
        row = list(category.__dict__.values())
        row[2] = format_bytes(row[2])
        row[3] = format_bytes(row[3])
        table.add_row(row)
    table.sortby = 'ID'
    logger.info(f"\n{table}")

    categories = list(map(lambda x: x._display_name, device.categories))
    categories_rx = list(map(lambda x: x._rx, device.categories))
    categories_tx = list(map(lambda x: x._tx, device.categories))
    plt.simple_stacked_bar(categories, [categories_rx, categories_tx], width=100, labels=['rx', 'tx'],
                           title=f'Categories - {device.ip}')
    plt.show()


def main():
    content: list[str] = get_file_content()

    # filter send bucket lines
    buckets_lines: list[str] = [line for line in content if "combine_and_send" in line]

    # filter json content
    buckets: list[dict] = content_filter(buckets_lines)

    devices_data: DevicesData = DevicesData()
    for bucket in buckets:
        bucket_filter(devices_data, bucket)

    logger.info(dumps(devices_data.__dict__(), indent=4))

    for device in devices_data.devices:
        logger.info(f"Device: {device.ip}")
        if device.services:
            print_services(device)
        if device.categories:
            print_categories(device)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-lfp', '--log-file-path', type=str, help="Buckets file path")
    parser.add_argument('-cfp', '--classification-file-path', type=str, help="classification file path", default=None)
    args = parser.parse_args()
    log_file_path = args.log_file_path
    classification_file_path = args.classification_file_path

    main()
