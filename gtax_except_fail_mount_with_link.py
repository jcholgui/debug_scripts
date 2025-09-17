import re
import typing
import os
import subprocess
import json
import random
from datetime import datetime

mounted = "/root/Y"
gtax_rcv_dat_logs_path = f"{mounted}/rcv_dat_logs/automated/STAX_Guadalajara_QA"
gtax_test_link = "http://stax-mzm-qa.elements.local/#/jobs/{job_id}#task_tests_{test_id}"
jobset_sessions_link = "http://stax-mzm-qa.elements.local/#/jobset_sessions/{job_session}?tab=jobs"
test_plan_id = None
current_day = datetime.now().day
current_month = datetime.now().month

RULE_ID_REGEX = '^[A-Z]{4}\_[0-9|A-Z]{4}'
RANGE_FORMAT = "\d+\-?\d*"
EXCEPTIONS_FILE_NAME = 'exceptions.log'
RESULTS_FILE_NAME = 'results.log'
TEST_JSON_DATA = 'test_env_data.json'
CMD_SUCCED = 0

class TestwFile:
    def __init__(self, test_id, job_id) -> None:
        self.id = test_id
        self.job_id = job_id
        self.test_path = None
        self.name = None
        self.sut = None
        self.file_tail = None        
        self.gtax_link =  self.__get_gtax_test_link()
        self.failed_rule_ids = []

    def __get_gtax_test_link(self) -> None:
        test_id = self.id.replace("/", "")
        return gtax_test_link.format(job_id=self.job_id, test_id=test_id)

    def get_test_name(self):
        global test_plan_id
        test_json_data_path = f"{self.test_path}/{TEST_JSON_DATA}"
        if not os.path.isfile(f"{test_json_data_path}"):
            return
        std_err, std_out = subprocess.getstatusoutput(f'cat {test_json_data_path}')
        if std_err != CMD_SUCCED:
            return
        json_info = json.loads(std_out)
        test_name = json_info['test_name']
        test_sut = json_info['name']
        if not test_plan_id:
            test_plan_id = json_info['test_plan_id']
        self.name = test_name
        self.sut = test_sut

    def get_file_tail(self):
        exceptions_path = f"{self.test_path}/{EXCEPTIONS_FILE_NAME}"
        std_err, std_out = subprocess.getstatusoutput(f'tail -n 4 {exceptions_path}')
        if std_err != CMD_SUCCED:
            return
        strip_std_out = std_out.strip()
        self.file_tail = strip_std_out

    def get_fail_test_ids(self):
        results_path = f"{self.test_path}/{RESULTS_FILE_NAME}"
        fail_line_err, fail_line = subprocess.getstatusoutput(f'tac {results_path} | grep -wnm 1 Fail: | cut -d":" -f 1')
        if fail_line_err != CMD_SUCCED or fail_line == '':
            return
        ignore_line_err, ignore_line = subprocess.getstatusoutput(f'tac {results_path} | grep -wnm 1 Ignore: | cut -d":" -f 1')
        if ignore_line_err == CMD_SUCCED and ignore_line != '':
            # stringa = f'sed -n {fail_line},{ignore_line}p {results_path}'
            ignore_line = int(fail_line) - int(ignore_line)
            stringa = f'tail -n {fail_line} {results_path} | head -n {ignore_line}'
        else:
            # stringa = f'sed \'1,{fail_line}d\' {results_path}' # sed -n 229,203p results.log | grep -Eo '^[A-Z]{4}\_[0-9|A-Z]{4}'
            stringa = f'tail -n {fail_line} {results_path}'
        failed_rule_ids_err, failed_rule_ids = subprocess.getstatusoutput(f'{stringa} | grep -Eo \'{RULE_ID_REGEX}\'')

        if failed_rule_ids_err == CMD_SUCCED and failed_rule_ids != '':
            failed_rule_ids = failed_rule_ids.split("\n")
            self.failed_rule_ids = failed_rule_ids
            return True
        return False

class Job:
    def __init__(self, id) -> None:
        self.id = id
        self.test_ids = None
        self.tests_w_exceptions: list[TestwFile] = []
        self.tests_w_fails: list[TestwFile] = []
        self.failed_rule_ids = []
        self.how_many_test_w_exception = 0

    def add_test_w_exception(self, test: TestwFile) -> None:
        self.tests_w_exceptions.append(test)

    def add_test_w_fails(self, test: TestwFile) -> None:
        self.tests_w_fails.append(test)

    @property
    def has_tests_w_exceptions(self) -> bool:
        self.how_many_test_w_exception = len(self.tests_w_exceptions)
        return self.how_many_test_w_exception > 0

    @property
    def has_tests_w_fails(self) -> bool:
        return len(self.tests_w_fails) > 0

    def get_all_failed_rule_ids(self, failed_rule_dict = {}) -> None:
        if not self.tests_w_fails:
            return
        for test in self.tests_w_fails:
            for rule_failed in test.failed_rule_ids:
                if rule_failed not in failed_rule_dict:
                    failed_rule_dict[rule_failed] = (1, [test.gtax_link])
                else:
                    count, link_list = failed_rule_dict[rule_failed]
                    count = count + 1
                    link_list.append(test.gtax_link)
                    failed_rule_dict[rule_failed] = (count, link_list)


def ask_job_id_range() -> str:
    '''
    Generally in a Job session, job ids are sequence,
    this function asks for the max and min limit.
    '''
    print(f"\n\t Look for {EXCEPTIONS_FILE_NAME} file in GTAX jobs")
    print("Ex. 51800-51767 or 51767")
    range_to_find = input("Job id range: ")
    return range_to_find

def get_job_ids_by_id_range(id_range:str) -> typing.Iterable:
    '''
    Gets max and min limit of ask_job_id_range() string pattern.
    '''
    ranges = id_range.split("-")
    int_ranges = [int(rang) for rang in ranges]

    if len(int_ranges) > 1:
        max_limit = int_ranges[0]
        min_limit = int_ranges[-1]        
        if min_limit > max_limit:
            min_limit, max_limit = max_limit, min_limit
        return range(max_limit, min_limit - 1, -1)
    else:
        return int_ranges

def get_test_ids_by_job_id(job_ids: typing.Iterable) -> list:
    jobs = []
    print("\nGetting tests id for every job")
    for job_id in job_ids:
        job_id_path = f"{gtax_rcv_dat_logs_path}/{job_id}" 
        if not os.path.isdir(gtax_rcv_dat_logs_path):
            print(f"Unable to get: {job_id_path}")
            continue
        std_err, std_out = subprocess.getstatusoutput(f'ls {job_id_path}')
        if std_err == CMD_SUCCED:
            test_ids = std_out.split("\n")
            job_instance = Job(job_id)
            job_instance.test_ids = test_ids
            jobs.append(job_instance)
    return jobs

def look_for_file(jobs) -> None:
    print(f"Total jobs to check: {len(jobs)}")

    for number, job in enumerate(jobs, start=1):
        print(f"- Job {job.id} ({number}): ")
        tests = job.test_ids
        total_test = len(tests)
        for test_num, test_id in enumerate(tests, start=1):
            arrows = "=" * test_num
            print(f"{arrows}> {test_num}/{total_test} tests", end="\r")
            test_id_path = f"{gtax_rcv_dat_logs_path}/{job.id}/{test_id}"
            test_instance = TestwFile(test_id, job.id)
            test_instance.test_path = test_id_path
            if os.path.isfile(f"{test_id_path}/{EXCEPTIONS_FILE_NAME}"):                                    
                test_instance.get_test_name()
                test_instance.get_file_tail()
                job.add_test_w_exception(test_instance)
            if os.path.isfile(f"{test_id_path}/{RESULTS_FILE_NAME}"):
                if test_instance.get_fail_test_ids():
                    job.add_test_w_fails(test_instance)
        print("\n")

def file_info(file):    
    if info:
        file.write(f"BIT {current_month}/{current_day} - {info}\n")
    if job_session:
        file.write(f'{jobset_sessions_link.format(job_session=job_session)}\n')
        job_session_text = f'Job session {job_session}'
    else:
        job_session_text = f'Job ids [{id_range}]'

    if test_plan_id:
        file.write(f"{test_plan_id}\n\n")
    file.write('------------------------------------------------------------------------------------------------------------------------\n')
    file.write(f"This file contains gtax links and names of tests that got {EXCEPTIONS_FILE_NAME} file in {job_session_text}.\n")
    file.write("*If a Job was cancelled, it won't get the links if any\n")
    file.write("**If a Test failed due a manager error (wrong override set, drive dropped, etc.) it won't get the link either\n")
    file.write('------------------------------------------------------------------------------------------------------------------------\n')

def print_exceptions(file, jobs_w_files: typing.Iterable[Job], num_of_exceptions=0):
    if not jobs_w_files:
        return
    file.write(f"\n***************************** Exceptions found ({num_of_exceptions}) *****************************")
    for job in jobs_w_files:
        sut_set = False
        file.write(f"\n\n--- JOB ID: {job.id} ---")
        for test in job.tests_w_exceptions:
            if test.sut and not sut_set:
                file.write(f"\t{test.sut}")
                sut_set = True
            if test.name:
                file.write(f"\nTEST NAME: {test.name}")
            file.write(f"\n\t\t{test.gtax_link}\n")
            if test.file_tail:
                file.write(f"\n{EXCEPTIONS_FILE_NAME} ------------------------------------------------------------")
                file.write(f"\n{test.file_tail}")
                file.write("\n----------------------------------------------------------------------------\n")
            else:
                file.write(f"\n{EXCEPTIONS_FILE_NAME} empty\n")
                file.write("\n----------------------------------------------------------------------------\n")
    file.write("\n")

def print_fails(file, jobs_w_fails: typing.Iterable[Job]) -> None:
    if not jobs_w_fails:
        return
    failed_rule_dict = {}
    for job in jobs_w_fails:
        job.get_all_failed_rule_ids(failed_rule_dict)

    if failed_rule_dict:
        file.write(f"\n--- Number of times rule fail was found ---")
        file.write(f"\n*One link per rule\n\n")

        count_sorted = dict(sorted(failed_rule_dict.items(), key=lambda item: item[1], reverse=True))
        for rule_id, count in count_sorted.items():
            file.write(f"{rule_id} - {count[0]}\n")
            link = random.choice(count[1])
            file.write(f"Link: {link}\n")

if __name__ == '__main__':
    if not os.path.isdir(gtax_rcv_dat_logs_path):
        print("\t * Need to mount //elements.local/PV/RCV_Logs")
        print("Exit ...")
        exit()

    id_range = ask_job_id_range()

    if not re.match(RANGE_FORMAT, id_range):
        print("Wrong range, not valid format")
        exit()

    # Ex. tc_v5.13.1+core_v5.6.3 (info added in the final file)
    info = input("Add branches versions: ")
    # Ex. 25467 (info added in the final file)
    job_session = input("Job session: ")
    job_ids = get_job_ids_by_id_range(id_range)
    jobs = get_test_ids_by_job_id(job_ids)
    if not jobs:
        print(f"\nUnable to get any test, early exit")
        exit()
    look_for_file(jobs)
    jobs_w_exceptions = list(filter(lambda job: job.has_tests_w_exceptions, jobs))
    jobs_w_fails = list(filter(lambda job: job.has_tests_w_fails, jobs))

    if not jobs_w_exceptions and not jobs_w_fails:
        print(f"\n\tNothing to print, exiting ...")
        exit()

    # Number of exceptions
    if jobs_w_exceptions:
        num_of_exceptions = sum([job.how_many_test_w_exception for job in jobs_w_exceptions])

    if test_plan_id:
        file_name = f'BIT_{current_month}_{current_day}_{test_plan_id}'
    else:
        file_name = id_range

    file = open(f"{file_name}_exceptions.txt", "a")
    file_info(file)
    print_exceptions(file, jobs_w_exceptions, num_of_exceptions)
    print_fails(file, jobs_w_fails)
    file.close()
    print("Finished")
