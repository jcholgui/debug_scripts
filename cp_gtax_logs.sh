#!/bin/bash

qa_mount_point="/root/Y/rcv_dat_logs/automated/STAX_Guadalajara_QA"
utf_mount_point="/root/Y/rcv_dat_logs/automated/STAX_Guadalajara_UTF"
# Files to get in the main directory
files=("exceptions.log" "results.log" "test_env_data.json" "summary.log" "parse_summary.txt")
# Files to get in the SN directory
files_sn=("debug.log.gz" "debug.log" "dss_dump_end.log" "dss_dump_init.log" "drive_info.json" "da_dump_init.log" "da_dump_end.log" "drive_config.json" "drive_info.json")

function display_menu_and_get_option() {
    echo "Select instance:"
    echo "1) STAX QA"
    echo -e "2) STAX UTF\n"

    read -p "Enter your choice: " choice

    case $choice in
        1)return 1;;
        2)return 2;;
        *)return 0;;
    esac
}
display_menu_and_get_option
mount_point=$?
if [ "${mount_point}" -eq 1 ]; then
    mount_point="${qa_mount_point}"
elif [ "${mount_point}" -eq 2 ]; then
    mount_point="${utf_mount_point}"
else
    echo "Not valid option, Exiting..."
    exit
fi

if ! [ -d "${mount_point}" ]; then
    echo "Mount elements RCV logs first"
    exit
fi

read -p "Enter job id: " job_id

if ! [ -d "${mount_point}/${job_id}" ]; then
    echo "That job id doesnt exist"
    exit
fi

read -p "Test: " test
if [ -z "${test}" ]; then
    test=0
fi

job_test_dir="${mount_point}/${job_id}/${test}/"
if ! [ -d "${job_test_dir}" ]; then
    echo "That test doesnt exist or is too big so is in a zip"
    echo "Check: ls ${mount_point}/${job_id}"
    exit
fi

directory=${job_id}_${test}
mkdir ${directory}

cd "${job_id}_${test}"

# Files defined at top
echo "Getting logs ..."
for i in "${files[@]}"
do
   `cp ${job_test_dir}${i} . &> /dev/null`
done

# Get Drive SN
sn=`find ${job_test_dir} -maxdepth 1 -type d | grep -E '.*[A-Z0-9]$' | rev | cut -d'/' -f1 | rev`

# Files defined at top
for i in "${files_sn[@]}"
do
   `cp ${job_test_dir}${sn}/${i} . &> /dev/null`
done

# Unzip debug file if there is any
if [ -f "debug.log.gz" ]; then
    gzip -d debug.log.gz
fi 

# Failing Batch Seed Numbers
fbn=`grep 'Failing Batch Seed Numbers :' results.log | grep -Eo '[0-9]{2}[0-9a-z]{6}' | tr [:lower:] [:upper:]`

# Copy only failing dat files
#for i in $fbn
#do
#   `cp ${job_test_dir}${sn}/content_components/coverage/drive_access_tracker.*${i}.log . &> /dev/null`
#done
`cp ${job_test_dir}${sn}/content_components/coverage/drive_access_tracker.*.log . &> /dev/null`        # Copy all dat files

# If exception file exists, get dat aborted if any
if [ -f "exceptions.log" ]; then
    `cp ${job_test_dir}${sn}/content_components/coverage/drive_access_tracker.*.log.aborted . &> /dev/null`
fi

# Get command to scp to your system
user=`whoami`
ip=`hostname -I | sed 's/[[:blank:]]*$//'`
pdirectory=`pwd`

# echo "*Get the logs by using: scp -r ${user}@${ip}:${pdirectory} ."
echo "*Check: ls ${mount_point}/${job_id}"
echo "${directory}"
