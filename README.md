## Description
This program is meant to be used to sift through the student data stored at the CAE Center and determine whether or not the data can be archived. When the program runs, it will compile information about each user associated with each data directory in order to make a decision. This information is pulled from main campus ldap as well as the modification timestamp on the directory. It will also calculate the size of each directory and provide simple statistics about how much data is being archived.

## Data Retention Policy
There are three configurable retention policies that the program enforces. These are defined in the config file (See 'Configuration' for details) and these are their current values. 

``data_retention_months_after_expiration`` : 12

``data_retention_months_after_access`` : 24
 
``data_retention_months_of_archive`` : 12

## Configuration

``data_retention_months_after_expiration`` If the user has an expiration date in ldap, this is how many months their data will be kept after that date.

``data_retention_months_after_access`` If the user does not have an expiration date present in ldap, then the program will look at the last date that their data was modified. This is how many months after that date that their data will be kept.

``data_retention_months_of_archive`` When the program decides it safe to get rid of a user's data, it does not delete it, it archives it into a massive zip file. The zip file will then be kept for this many months.

``student_data_path`` The root directory where the student data is held.

``archive_path`` The root directory where the archives should be placed.

``print_user_info`` Print information about the users to the command line.

``confirm_before_archive`` Prompt the user for confirmation before archiving data.

``disable_archiving`` Disable/Enable archiving all together.

``file_ignore_filer`` Comma delimited list of folder/file names that should be ignored in the student_data_path.

``user_limit`` Limit the program to only work with so many users. Set to None to make unlimited.

``runtime_stats`` Set to False to disabled stats while running. Set to an integer to display runtime stats every so many users.

``verbose_username`` Be more verbose about the user names that are being handled.

``process_threads`` Number of threads to use in the thread pool when calculating user folder size. 

## Usage

``~/Student_Data_Retention_Enforcer/__init__.py``
Where ``~/`` is the install directory.

On Alva, it is installed in ``/opt/Student_Data_Retention_Enforcer`` so to run it from there, login and run the following commands:
* ``sudo su``
* ``cd /opt/Student_Data_Retention_Enforcer``
* ``./__init__.py``


## Manifest
After data is archived, a manifest file will be written to the ``archive_path``. This file will be outside of the .zip file and will be named with the date that the data was archived. This file will contain detains about the user data that is in the archive. If we need to restore a user's data from an archive, we can look in the manifest to confirm that the user's data is in there before decompressing the archive. The manifest files will also be kept even after an old archive is deleted in case we need to confirm that a user's data is no longer available. 
