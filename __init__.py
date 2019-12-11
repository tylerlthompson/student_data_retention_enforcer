#!/usr/bin/python3

import os
import getpass
import sys
import shutil
import json
import calendar
import datetime
from time import time
from time import sleep
from pathlib import Path

from resources.config import config
from resources.ldap_config import config as ldap_config
from resources.User import User
from resources.Tools import Tools
from resources.ThreadedUserProcess import ThreadedUserProcess
from SimpleLdapLib import SimpleLdap

time_stamp = '{0}_{1}'.format(str(datetime.datetime.today().date()).replace('-', '_'),
                              datetime.datetime.today().strftime('%H_%M'))
archive_path = '{0}/{1}'.format(config['archive_path'], time_stamp)


def main():
    start_time = time()

    # make sure we are running as root
    if getpass.getuser() != 'root':
        print('Program must be run as root. Exiting...')
        sys.exit(0)

    print('Scanning student data directory...')
    try:
        uids = os.listdir(config['student_data_path'])
    except FileNotFoundError:
        print("Data path does not exist: {0} Exiting...".format(config['student_data_path']))
        sys.exit(0)

    # filter user ids
    for uid in uids:
        if uid in config['file_ignore_filter'].split(','):
            uids.remove(uid)
    uids.sort()

    # apply user limit
    if config['user_limit']:
        print('Limiting information compilation to {0} users. Edit the config to change this.'
              .format(config['user_limit']))
        real_uids = []
        i = 0
        for uid in uids:
            i += 1
            real_uids.append(uid)
            if i == config['user_limit']:
                break
        uids = real_uids

    # lookup all user information
    users = lookup_user_ldap_info(uids=uids)

    # process user information and determine user status
    users_to_archive = process_users(users=users)
    number_to_archive = len(users_to_archive)

    # calculate archive file size
    archive_file_size = 0
    for user in users_to_archive:
        archive_file_size += user.folder_size
    archive_file_size = round(archive_file_size, 3)

    # print all user information
    if config['print_user_info'] and config['verbose_username']:
        Tools().pretty_print_objects(objects=users, title='Users', objFilter='folder_path,folder_size')

    # archive users if there are any to archive
    if users_to_archive:
        if config['print_user_info']:
            Tools().pretty_print_objects(objects=users_to_archive, title='Users to Archive', objFilter='folder_path')

        print("File size of archive before compression: {0} MB".format(archive_file_size))
        print("Number of users to be archived: {0}".format(number_to_archive))
        if not config['disable_archiving']:

            if config['confirm_before_archive']:
                user_input = input('About to archive {0} users. Continue? [yes|no]: '.format(number_to_archive))
                if user_input != 'yes':
                    print('We will meet again. Exiting...')
                    sys.exit(0)

            # archive_users(users=users_to_archive, archive_size=archive_file_size)
            # archive the data in chunks to keep zip files from getting to big.
            users_to_archive_in_chunks, archive_size_chunks = divide_users_on_directory_size(users=users_to_archive)
            for users in users_to_archive_in_chunks:
                archive_index = users_to_archive_in_chunks.index(users)
                print("Archive Index: {0}".format(archive_index))
                archive_users(users=users, archive_size=archive_size_chunks[archive_index], archive_index=archive_index)

        else:
            print("Archiving is disabled in the config, skipping archive step...")
    else:
        print('No users found that could be archived.')

    # remove previous archives
    remove_old_archive()

    # calc total runtime
    if config['runtime_stats']:
        run_time_seconds = (time() - start_time)
        run_time_minuets = int(run_time_seconds / 60)
        if run_time_minuets == 0:
            run_time = int(run_time_seconds)
            units = 'seconds'
        else:
            run_time = run_time_minuets
            units = 'minuets'
        print("Total runtime: {0} {1}".format(run_time, units))

    print('Done.')


def process_users(users):
    """
    Process the user's information. Mainly calculate disk space used. Uses thread pooling so runtime stats are not
    always very accurate at calculating estimated time left.
    :param users: A list of Users
    :return: A list of Users
    """
    users_to_archive = []
    threads = []
    done_threads = []
    thread_pool = []
    runtime_sum = 0
    users_processed = 0

    print('Processing user information...')

    # prepare threads
    for user in users:
        user.user_status = determine_user_status(user=user)
        if not user.user_status:
            users_to_archive.append(user)
            threads.append(ThreadedUserProcess(user=user))

    # determine number of threads to use
    process_threads = config['process_threads']
    if len(threads) < process_threads:
        process_threads = len(threads)

    # fill thread pool
    for i in range(process_threads):
        thread_pool.append(threads.pop())

    # start all threads in pool
    for thread in thread_pool:
        thread.start()

    # manage the thread pool
    while threads:
        sleep(0.2)
        for thread in thread_pool:
            if not thread.is_alive():

                # show runtime stats
                if config['runtime_stats']:
                    runtime_sum += thread.runtime
                    users_processed += 1
                    if users_processed % config['runtime_stats'] == 0:
                        # calc average
                        average_runtime = runtime_sum / users_processed

                        # calc time left
                        users_remaining = len(users_to_archive) - users_processed
                        seconds_left = users_remaining * average_runtime
                        minuets_left = int(seconds_left / 60)
                        units = 'minuets'
                        time_left = minuets_left
                        if minuets_left == 0:
                            time_left = int(seconds_left)
                            units = 'seconds'

                        print('Average runtime for user processing: {0:03d} milliseconds,'
                              ' Estimated time left: {1:02d} {2}, Users remaining: {3:05d}'.
                              format(int(average_runtime * 1000), time_left, units, users_remaining), end='\r')

                # shift threads in and out of thread pool
                done_threads.append(thread)
                thread_pool.remove(thread)
                try:
                    new_thread = threads[0]
                    thread_pool.append(new_thread)
                    threads.pop(0)
                    new_thread.start()
                except IndexError:
                    pass

    # wait for the last threads to finish
    last_threads_running = True
    while last_threads_running:
        sleep(0.2)
        last_threads_running = False
        for thread in thread_pool:
            if thread.is_alive():
                last_threads_running = True
            else:
                # show runtime stats
                if config['runtime_stats']:
                    if thread.runtime != 0:
                        runtime_sum += thread.runtime
                        users_processed += 1
                        thread.runtime = 0
                        if users_processed % config['runtime_stats'] == 0:
                            # calc average
                            average_runtime = runtime_sum / users_processed

                            # calc time left
                            users_remaining = len(users_to_archive) - users_processed
                            seconds_left = users_remaining * average_runtime
                            minuets_left = int(seconds_left / 60)
                            units = 'minuets'
                            time_left = minuets_left
                            if minuets_left == 0:
                                time_left = int(seconds_left)
                                units = 'seconds'

                            print('Average runtime for user processing: {0:03d} milliseconds,'
                                  ' Estimated time left: {1:02d} {2}, Users remaining: {3:05d}'.
                                  format(int(average_runtime * 1000), time_left, units, users_remaining), end='\r')
    if config['runtime_stats']:
        print()

    # join all threads
    for thread in done_threads:
        thread.join()

    return users_to_archive


def remove_old_archive():
    """
    Searches archive directory for old archives and deletes them if they are out of retention
    :return: None
    """
    try:
        for archive in os.listdir(config['archive_path']):
            archive_date_info = archive.split('_')
            try:
                # skip manifest files
                if archive_date_info[5] == 'manifest.json':
                    continue
            except (ValueError, IndexError):
                pass
            try:
                year = int(archive_date_info[0])
                month = int(archive_date_info[1])
                day = int(archive_date_info[2])
            except (ValueError, IndexError):
                continue
            archive_date = datetime.datetime(year=year, month=month, day=day)
            if not check_expiration(expiration_date=archive_date,
                                    retention_months=config['data_retention_months_of_archive']):
                delete_archive_path = '{0}/{1}'.format(config['archive_path'], archive)
                print('Removing old archive: {0}'.format(delete_archive_path))
                os.remove(path=delete_archive_path)
    except FileNotFoundError as e:
        print("{0} Skipping removal of old archive...".format(e))


def divide_users_on_directory_size(users):
    users_to_archive = []
    user_chunk = []
    archive_size_chunks = []
    archive_size = 0
    for user in users:
        archive_size += user.folder_size
        user_chunk.append(user)
        if archive_size >= config['max_archive_size']:
            users_to_archive.append(user_chunk)
            archive_size_chunks.append(archive_size)
            user_chunk = []
            archive_size = 0
    if user_chunk:
        users_to_archive.append(user_chunk)
        archive_size_chunks.append(archive_size)
    return users_to_archive, archive_size_chunks


def archive_users(users, archive_size, archive_index=0):
    """
    Archive user data into a zip file
    :param users: a list of User objects
    :param archive_size: the size of the archive
    :param archive_index: the index of the archive if there is more than one
    :return: None
    """
    print('Archiving user data...')
    new_archive_path = '{0}_{1}'.format(archive_path, archive_index)
    # make new directory for archive
    try:
        os.mkdir(new_archive_path)
    except FileExistsError as e:
        print('{0} failed to make new archive. Skipping user data archive...'.format(e))
        return

    # move user data into archive
    for user in users:
        if config['verbose_username']:
            print("Archiving user: {0}".format(user.uid))
        shutil.move(src=user.folder_path, dst=new_archive_path)

    # write manifest file
    print("Writing manifest...")
    manifest = {'0_run_stats': {'date': time_stamp, 'users_archived': len(users),
                                'archive_size': '{0} MB'.format(archive_size)}}
    for user in users:
        manifest[user.uid] = user.__dict__
        if isinstance(user.wmu_student_expiration, datetime.datetime):
            manifest[user.uid]['wmu_student_expiration'] = str(user.wmu_student_expiration.strftime('%D'))
        if isinstance(user.wmu_employee_expiration, datetime.datetime):
            manifest[user.uid]['wmu_employee_expiration'] = str(user.wmu_employee_expiration.strftime('%D'))
        if isinstance(user.modify_date, datetime.datetime):
            manifest[user.uid]['modify_date'] = str(user.modify_date.strftime('%D'))
    write_json_file(file_path='{0}/{1}'.format(config['archive_path'],
                                               '{0}_{1}_manifest.json'.format(time_stamp, archive_index)),
                    json_data=manifest)

    # compress archive
    print('Compressing archive...')
    fix_directory_timestamps(folder_path=new_archive_path)
    try:
        shutil.make_archive(base_name=new_archive_path,
                            format='zip',
                            root_dir=config['archive_path'],
                            base_dir="{0}_{1}".format(time_stamp, archive_index))
    except (UnicodeEncodeError, ValueError) as e:
        print("Compressing archive failed: {0} Please compress the archive manually. {1}_{2}".format(e, time_stamp,
                                                                                                     archive_index))
        return

    # remove uncompressed archive
    shutil.rmtree(path=new_archive_path)


def fix_directory_timestamps(folder_path):
    """
    Looks at the modification date of all files in a folder and sets it to today if it is currently set to before 1980
    :param folder_path: The directory to work with
    :return: None
    """
    for path, dirs, files in os.walk(folder_path):
        for f in files:
            fp = os.path.join(path, f)
            try:
                if datetime.datetime.fromtimestamp(os.stat(fp).st_mtime).year <= 1980:
                    Path(fp).touch()
            except (FileNotFoundError, OSError):
                pass
        for d in dirs:
            fp = os.path.join(path, d)
            try:
                if datetime.datetime.fromtimestamp(os.stat(fp).st_mtime).year <= 1980:
                    Path(fp).touch()
            except (FileNotFoundError, OSError):
                pass


def determine_user_status(user):
    """
    Determines if a user's data should be kept or not
    :param user: A User object
    :return: True - user's data should be kept | False - user's data should be deleted
    """
    if user.wmu_enrolled:
        return True
    elif user.wmu_enrolled == None:
        if not user.inet_user_status:
            return False
        else:
            return determine_user_status_not_enrolled(user=user)
    else:
        return determine_user_status_not_enrolled(user=user)


def determine_user_status_not_enrolled(user):
    """
    Determines if a user's data should be kept or not starting at the student expiration point on the tree
    Should only be called from determine_user_status()
    :param user: A User object
    :return: True - user's data should be kept | False - user's data should be deleted
    """
    # student expiration object is none
    if not user.wmu_student_expiration:

        # employee expiration object is none
        if not user.wmu_employee_expiration:

            # check modification date
            return check_expiration(expiration_date=user.modify_date,
                                    retention_months=config['data_retention_months_after_access'])

        # employee expiration object exists
        else:

            # return expiration status
            return check_expiration(expiration_date=user.wmu_employee_expiration,
                                    retention_months=config['data_retention_months_after_expiration'])

    # student expiration object exists
    else:

        # student expiration is within retention
        if check_expiration(expiration_date=user.wmu_student_expiration,
                            retention_months=config['data_retention_months_after_expiration']):
            return True

        # student expiration is out of retention
        else:

            # employee expiration object is none
            if not user.wmu_employee_expiration:
                return False

            # employee expiration object exists
            else:

                # return expiration status
                return check_expiration(expiration_date=user.wmu_employee_expiration,
                                        retention_months=config['data_retention_months_after_expiration'])


def check_expiration(expiration_date, retention_months):
    """
    Checks expiration date against today's date and returns true or false based on retention months
    :param expiration_date: Date something expires
    :param retention_months: Number of months past today the expiration is still good
    :return: True - within retention | False - out of retention
    """
    # add retention months to expiration date
    month = expiration_date.month - 1 + retention_months
    year = expiration_date.year + month // 12
    month = month % 12 + 1
    day = min(expiration_date.day, calendar.monthrange(year, month)[1])
    true_expiration = datetime.datetime(year=year, month=month, day=day)

    # compare true expiration to today
    if (true_expiration - datetime.datetime.today()).days > 0:
        return True
    else:
        return False


def lookup_user_ldap_info(uids):
    """
    Look up user information from ldap
    :param uids: a list of user IDs
    :return: a list of User objects
    """
    print('Compiling information on users...')
    ldap_d = SimpleLdap()
    ldap_d.config = ldap_config
    if not ldap_d.bind_server():
        print("Failed to bind to ldap server. Exiting...")
        sys.exit(0)

    ldap_users = []
    runtime_sum = 0
    users_processed = 0
    for uid in uids:

        start_time = time()

        ldap_user = ldap_d.search(search_filter="(uid={0})".format(uid))
        folder_path = '{0}{1}{2}'.format(config['student_data_path'], '/', uid)
        if config['verbose_username']:
            print('Compiling information on user: {0}'.format(uid))

        if not ldap_user:
            new_user = User(uid=uid,
                            full_name="User not in ldap",
                            wmu_enrolled=None,
                            inet_user_status='deleted',
                            wmu_student_expiration=None,
                            wmu_employee_expiration=None,
                            modify_date=datetime.datetime.fromtimestamp(os.stat(folder_path).st_mtime),
                            folder_size=None,
                            folder_path=folder_path)
        else:
            new_user = User(uid=uid,
                            full_name=ldap_user['displayName'],
                            wmu_enrolled=ldap_user['wmuEnrolled'],
                            inet_user_status=ldap_user['inetUserStatus'],
                            wmu_student_expiration=ldap_user['wmuStudentExpiration'],
                            wmu_employee_expiration=ldap_user['wmuEmployeeExpiration'],
                            modify_date=datetime.datetime.fromtimestamp(os.stat(folder_path).st_mtime),
                            folder_size=None,
                            folder_path=folder_path)
        ldap_users.append(new_user)

        # show runtime stats
        if config['runtime_stats']:
            run_time = time() - start_time
            users_processed += 1
            runtime_sum += run_time

            # only show stats every so many users
            if users_processed % config['runtime_stats'] == 0:
                # calc average
                average_runtime = runtime_sum / users_processed

                # calc time left
                users_remaining = len(uids) - users_processed
                seconds_left = users_remaining * average_runtime
                minuets_left = int(seconds_left / 60)
                units = 'minuets'
                time_left = minuets_left
                if minuets_left == 0:
                    time_left = int(seconds_left)
                    units = 'seconds'

                print('Average runtime for information compilation: {0:03d} milliseconds, '
                      'Estimated time left: {1:02d} {2}, Users remaining: {3:05d}'.
                      format(int(average_runtime * 1000), time_left, units, users_remaining), end='\r')
    if config['runtime_stats']:
        print()

    ldap_d.unbind_server()
    print('Total number of users processed: {0}'.format(len(uids)))
    return ldap_users


def write_json_file(file_path, json_data, indent=4, sort_keys=True):
    """
    Write a dictionary to a file in json format
    :param file_path: Path to file to write
    :param json_data: Dictionary to write
    :param indent: Number of spaces to indent
    :param sort_keys: Sort the dictionary before writing
    :return: None
    """
    write_text_file(file_path=file_path,
                    text_data=json.dumps(json_data, indent=indent, sort_keys=sort_keys))


def write_text_file(file_path, text_data):
    """
    Write text to a file.
    :param file_path: Path to file to write
    :param text_data: Text to write to file
    :return: None
    """
    file_path = os.path.abspath(file_path)
    try:
        with open(file_path, 'w') as write_file:
            write_file.write(text_data)
    except (FileExistsError, FileNotFoundError, PermissionError, OSError) as e:
        print("{0} Failed to write file path: {1}".format(e, file_path))


if __name__ == '__main__':
    main()
