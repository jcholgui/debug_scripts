import re
import os
from typing import List, Dict, Optional
from dataclasses import dataclass


NUM_FAILED_SQE = 8
NUM_SQE_BEFORE = 5

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
    sc: Optional[str] = None
    sct: Optional[str] = None

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

def populate_its_status(dat_entries: List[DATLine], sorted_previous_sqe_n: List[DATLine]):
    for previous_sqe in sorted_previous_sqe_n:
        cycle_id = previous_sqe.cycle_id
        cqe = filter(lambda dat_line: dat_line.cycle_id == cycle_id and dat_line.direction == "<==", dat_entries)
        if not cqe:
            continue
        cqe = next(cqe, None)
        if not isinstance(cqe, DATLine):
            return
        details = cqe.details
        param_matches = param_pattern.findall(details)
        param_dict = {m[0]: m[1] for m in param_matches}
        previous_sqe.sc = param_dict.get("SC", None)
        previous_sqe.sct = param_dict.get("SCT", None)

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

def get_sqe_details(failed_sqe: List[Dict[str, str]]):
    if not failed_sqe:
        return
    failed_sqe_details = [dat_line.details for dat_line in failed_sqe]
    return failed_sqe_details

def get_sqe_by_failed_rule(dat_entries: List[Dict[str, str]], rule: str, how_many_sqe:int = 5):
    if not rule:
        print("No rule provided")
        return

    failed_rule = list(filter(lambda dat_line: dat_line.rule == rule and dat_line.result == "Fail", dat_entries))
    failed_cycle_ids = [dat_line.cycle_id for dat_line in failed_rule]
    failed_sqe = list(filter(lambda dat_line: dat_line.cycle_id in failed_cycle_ids and dat_line.direction == "==>", dat_entries))
    return failed_sqe[:how_many_sqe]

def divide_sqe(sqe: str):
    param_dict = {}
    sqe = sqe.strip(" ")
    match = sqe_pattern.match(sqe)
    if match:
        entry = match.groupdict()
        param_matches = param_pattern.findall(entry["params"])
        param_dict = {m[0]: m[1] for m in param_matches}
        param_dict.update({"command":entry["command"]})
    return param_dict

def find_incidents(dicts):
    common_items = set(dicts[0].items())  # Start with items of the first dictionary
    for d in dicts[1:]:
        common_items &= set(d.items())  # Intersect items with subsequent dictionaries
    return dict(common_items)

def parse_sqe_details(failed_sqe: List[str] = []):
    if not failed_sqe:
        return
    parsed_sqe = []
    for sqe in failed_sqe:
        sqe_dicta = divide_sqe(sqe)
        parsed_sqe.append(sqe_dicta)

    return parsed_sqe

def get_sqe_similarities(parsed_sqe: List[str] = []):
    if not parsed_sqe:
        return
    incidents: Dict[str, str] = find_incidents(parsed_sqe)
    return incidents

def printr(Message, items):
    print(f"\n{Message}:")
    if isinstance(items, list):
        for i in items:
            print(i)
        return
    print(items)

def get_failed_commands(parsed_sqe):
    if not parsed_sqe:
        return
    commands = set([entry["command"] for entry in parsed_sqe])
    return commands

def get_sqe_before_failed_sqe_pair(dat_entries: List[DATLine], failed_sqe_by_rule, how_many_before=1):
    pair_sqe_previous_failed = []
    for dat_line in failed_sqe_by_rule:
        failed_sqe_timestamp = dat_line.timestamp
        previous_sqe = list(filter(lambda dat_line: dat_line.timestamp < failed_sqe_timestamp and dat_line.direction == "==>", dat_entries))
        if not previous_sqe:
            continue
        sorted_previous_sqe = sorted(previous_sqe, key=lambda dat_line: dat_line.timestamp, reverse=True)
        sorted_previous_sqe_n = sorted_previous_sqe[:how_many_before]
        populate_its_status(dat_entries, [dat_line])
        populate_its_status(dat_entries, sorted_previous_sqe_n)
        pair_sqe_previous_failed.append({"failed_command": dat_line, "previous_commands": sorted_previous_sqe_n})
    return pair_sqe_previous_failed


def main():
    directory = input("Directory: ")
    rule = input("Rule: ")
    if rule == '':
        return "No rule provided"

    dat_files: List[str] = get_drive_access_tracker_files(directory)
    if not dat_files:
        return
    print(f"\n*{len(dat_files)} DAT files detected to check for rule \"{rule}\"")

    dat_entries: List[DATLine] = get_entries(dat_files)
    while rule != '':
        print("--------------------------------------------------------------------")
        failed_sqe_by_rule: List[DATLine] = get_sqe_by_failed_rule(dat_entries, rule, how_many_sqe=NUM_FAILED_SQE)
        if not failed_sqe_by_rule:
            print("\n Exit: No failures with this rule were detected")
            return

        # ----- Print failed SQE command --------
        failed_sqe_details: List[str] = get_sqe_details(failed_sqe_by_rule)
        printr(f"Failed SQE, limit({NUM_FAILED_SQE})", failed_sqe_details)

        # ----- Print How many commands and which commands failed --------
        parsed_failed_sqes = parse_sqe_details(failed_sqe_details)

        commands = get_failed_commands(parsed_failed_sqes)
        print(f"\n*{len(commands)} command(s) failed with the same rule, {commands}")

        # ----- Print attributes in common in the failed commands --------
        similarities_insight: Dict[str, str] = get_sqe_similarities(parsed_failed_sqes)
        printr("- Incidents, attributes repeated in failed SQEs", similarities_insight)

        # ----- Print n SQE that happend before the failed SQE command --------
        failed_sqe_pairs: List[Dict[str, DATLine]] = get_sqe_before_failed_sqe_pair(dat_entries, failed_sqe_by_rule, how_many_before=NUM_SQE_BEFORE)
        print(f"\n- Previous {NUM_SQE_BEFORE} command(s) to the failing SQE")
        for num, previous_commands in enumerate(failed_sqe_pairs):
            failed_sqe: DATLine = previous_commands["failed_command"]
            print(f"\nFailed {num + 1}:\t\t{failed_sqe.filename}\t\t{failed_sqe.cycle_id}")            
            status_codes_to_print = " "
            if failed_sqe.sct and failed_sqe.sc:
                status_codes_to_print = f" (SCT: {failed_sqe.sct}, SC: {failed_sqe.sc}) "   
            print(f"{failed_sqe.timestamp} -{status_codes_to_print}{failed_sqe.details}\n")
            for num, previous_command in enumerate(previous_commands["previous_commands"]):
                status_codes_to_print = " "
                if previous_command.sct and previous_command.sc:
                    status_codes_to_print = f" (SCT: {previous_command.sct}, SC: {previous_command.sc}) "                
                print(f"{previous_command.timestamp} - {num + 1}){status_codes_to_print}{previous_command.details}")

        print("\n*Push Enter to exit")
        rule = input("- Any other rule you want to see: ")
        rule = ''
    else:
        print("\nFinished! ")

if __name__ == '__main__':
    main()
