import yaml
from multiprocessing import Process
import typing
import os

def save_process_info(process_objects: typing.List[Process], filename: str = "process_info.yaml"):
    """
    Save process information to a YAML file.
    """

    process_info = []
    for process in process_objects:
        info = {
            'name': process.name,
            'pid': process.pid,
            'is_alive': process.is_alive(),
            'exitcode': process.exitcode
        }
        process_info.append(info)

    with open(os.path.expanduser(filename), 'w') as file:
        yaml.dump(process_info, file, default_flow_style=False)
    print(f"Process information saved to {filename}")