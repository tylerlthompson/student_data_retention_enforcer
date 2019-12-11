
import datetime


class User(object):

    def __init__(self, uid, full_name, wmu_enrolled, inet_user_status, wmu_student_expiration, wmu_employee_expiration, modify_date, folder_size, folder_path):
        """
        User object with standardized values pulled from ldap
        :param uid: User ID
        :param full_name: user full name
        :param wmu_enrolled: True | False | None
        :param inet_user_status: True | False | None
        :param wmu_student_expiration: datetime object | None
        :param wmu_employee_expiration: datetime object | None
        :param modify_date: date of last modification to user data
        :param folder_size: size of user data in MB
        :param folder_path: path to user folder
        """
        self.uid = uid
        self.full_name = full_name
        self.modify_date = modify_date
        self.folder_size = folder_size
        self.folder_path = folder_path
        self.user_status = True
        if wmu_enrolled == []:
            self.wmu_enrolled = None
        else:
            self.wmu_enrolled = wmu_enrolled

        if inet_user_status == 'deleted':
            self.inet_user_status = False
        elif not inet_user_status:
            self.inet_user_status = None
        else:
            self.inet_user_status = True

        if not wmu_student_expiration:
            self.wmu_student_expiration = None
        else:
            if isinstance(wmu_student_expiration, datetime.datetime):
                self.wmu_student_expiration = wmu_student_expiration
            else:
                self.wmu_student_expiration = None

        if not wmu_employee_expiration:
            self.wmu_employee_expiration = None
        else:
            if isinstance(wmu_employee_expiration, datetime.datetime):
                self.wmu_employee_expiration = wmu_employee_expiration
            else:
                self.wmu_employee_expiration = None
