
config = {
    'student_data_path': '/DataStore/StudentData',
    'archive_path': '/DataStore/NetStore/Hoppiter Student Data Archive',
    'data_retention_months_after_expiration': 12,
    'data_retention_months_after_access': 24,
    'data_retention_months_of_archive': 12,
    'print_user_info': True,
    'confirm_before_archive': False,
    'disable_archiving': False,
    'file_ignore_filter': 'aquota.user,lost+found',
    'user_limit': None,  # set to None to disable
    'runtime_stats': None,  # set to None to disable
    'verbose_username': True,
    'process_threads': 50,
    'max_archive_size': 30000,  # max archive size in MB before compression
}
