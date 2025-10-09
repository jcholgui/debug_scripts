import re
import os
from typing import List, Dict, Optional
from dataclasses import dataclass


OMIT_DIR = [".vscode"]

SQE = "==>"
CQE = "<=="

@dataclass
class DATLine:
    timestamp: Optional[str] = None
    pid: Optional[str] = None
    rid: Optional[str] = None
    cycle_id: Optional[str] = None
    time_ms: Optional[str] = None
    direction: Optional[str] = None
    result: Optional[str] = None
    number: Optional[str] = None
    rule: Optional[str] = None
    details: Optional[str] = None
    filename: Optional[str] = None
    # CQE
    sc: Optional[str] = None
    sct: Optional[str] = None
    # SQE
    command: Optional[str] = None
    params: Optional[Dict[str, str]] = None

    def populate_more_details(self) -> None:
        if self.direction == SQE:
            self.populate_SQE_attr()
        elif self.direction == CQE:
            self.populate_CQE_attr()

    def populate_SQE_attr(self) -> None:
        param_dict = {}
        sqe = self.details.strip(" ")
        match = sqe_pattern.match(sqe)
        if match:
            entry = match.groupdict()
            param_matches = param_pattern.findall(entry["params"])
            param_dict = {m[0]: m[1] for m in param_matches}
            self.command = entry["command"]
            self.params = param_dict

    def populate_CQE_attr(self) -> None:
        details = self.details
        param_matches = param_pattern.findall(details)
        param_dict = {m[0]: m[1] for m in param_matches}
        self.sc = param_dict.get("SC", None)
        self.sct = param_dict.get("SCT", None)



dat_pattern = re.compile(
    r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)\s+'
    r'(?P<pid>\S+)\s+(?P<rid>\S+)\s+(?P<cycle_id>\S+)\s*'
    r'(?P<time_ms>\d*\.\d+)?\s*'
    r'(?P<direction>(==>|<==|===))\s*'
    r'(?P<result>(Fail|Pass))?\s*'
    r'(?P<number>#\d+\s+)?\s*'
    r'(?P<rule>([A-Z0-9_]+))?'
    r'(?P<details>.*)$'
)

sqe_pattern = re.compile(
    r'^(?P<command>\w+)\('
    r'(?P<params>[^)]+)\)'
)

param_pattern = re.compile(
    r'(\w+)=(0x[0-9a-fA-F]+|\d+|\w+)'
)


# Function to get all drive_access_tracker* files from a directory
def get_drive_access_tracker_files(directory):
    try:
        dat_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.startswith('drive_access_tracker')]
        return dat_files
    except FileNotFoundError:
        print("Exit: That directory was not found")

def get_entries(logfiles):
    dat_entries = []
    for logfile in logfiles:
        with open(logfile) as f:
            for line in f:
                match = dat_pattern.match(line)
                if match:
                    entry = match.groupdict()
                    entry['filename'] = os.path.basename(logfile)
                    new_dat_line = DATLine(**entry)
                    dat_entries.append(new_dat_line)
    return dat_entries

def parse_sqe_details(failed_sqe: List[DATLine]):
    for sqe in failed_sqe:
        sqe.populate_SQE_attr()


def get_last_sqe(dat_entries: List[DATLine]):
    command_to_look = input("Command: ")
    sqe_dat_entries = list(filter(lambda dat_line: dat_line.command == command_to_look, dat_entries))
    if not sqe_dat_entries:
        print("Command not found")
        return

    max_object = max(sqe_dat_entries, key=lambda obj: obj.timestamp)
    print(f"Last run of command {command_to_look}")
    print(f"{max_object.timestamp} - {max_object.details}")

def get_directory():
    script_directory = os.path.dirname(os.path.abspath(__file__))

    # List all directories in the script's directory
    directories = [item for item in os.listdir(script_directory) if os.path.isdir(os.path.join(script_directory, item))]
    directories_dict = {index: directory for index, directory in enumerate(directories, start=1) if directory not in OMIT_DIR}

    print("\n\tDirectories in the script's directory:")
    for index, directory in directories_dict.items():
        print(f"{index}) {directory}")
    print("\n")
    directory = int(input("Select: "))
    directory = directories_dict.get(directory)

    return directory


def main():
    directory = get_directory()
    dat_files: List[str] = get_drive_access_tracker_files(directory)
    if not dat_files:
        return
    print(f"\n*{len(dat_files)} DAT files detected to check")

    dat_entries: List[DATLine] = get_entries(dat_files)
    sqe_dat_entries = list(filter(lambda dat_line: dat_line.direction == SQE, dat_entries))    

    # ----- Print How many commands and which commands failed --------
    parse_sqe_details(sqe_dat_entries)

    sqe_entries = [dat_line for dat_line in sqe_dat_entries if dat_line.command == "directive_send"]
    sqe_entries_sorted_by_timestamp = sorted(sqe_entries, key=lambda dat_line: dat_line.timestamp)

    print("Repeated values and their counts:", sqe_entries_sorted_by_timestamp)

if __name__ == '__main__':
    main()
