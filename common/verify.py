import re


def verify_phone(phone: str) -> bool:
    return False if len(phone) != 11 or phone[0:2] not in ['13', '18', '15', '17'] else True


# def verify_username(username: str) -> bool:
#     """
#     verify username whether contain special charset
#     """
#     special_char = ('/', ' ', '[', ']', '"', '\\', '\'', '$', '%', '^', '*', '(', ')', '!', '~', '`')
#     for i in special_char:
#         if i in username:
#             return False
#     return True


def verify_in_array(arg1: str, array: tuple) -> bool:
    """
    verify arg1 whether in array
    """
    return True if arg1 in array else False


def verify_is_equal(x, y):
    """
    verify two object whether equal
    """
    return True if x == y else False


def verify_field(data: dict, field: tuple):
    """
    verify received dict data
    field format is ('field_name', field_type, verify_func)
    when verify_func is function then call the function verify field content
    when verify_func is tuple then tuple first element is verify_func, the second element is arg
    when field_name start with '*' mean the filed is necessary
    """
    if not isinstance(data, dict):
        return

    buff = {}

    # prevent all field is not necessary
    pass_flag = False

    if isinstance(field, tuple):
        for field_name, field_type, verify_param in field:

            if field_name[0] == '*':
                field_name = field_name[1:]

                if field_name not in data or not data[field_name]:
                    return 'field %s is necessary and can not be empty' % field_name

            if field_name not in data:
                continue

            if not isinstance(data[field_name], field_type):
                return 'field %s type wrong!' % field_name

            if verify_param and isinstance(verify_param, tuple) and len(verify_param) > 1:
                verify_func = verify_param[0]
                verify_arg = verify_param[1]
                verify_result = verify_func(data[field_name], verify_arg)

            if verify_param and hasattr(verify_param, '__call__'):
                verify_result = verify_param(data[field_name])

            if verify_param and not verify_result:
                return 'field %s verify failed!' % field_name

            if field_name in data:
                pass_flag = True

    if pass_flag:
        for i, _, _ in field:
            k = i.strip()
            if k[0] == '*':
                k = k[1:]

            if k in data and data[k]:
                if isinstance(data[k], str) and len(data[k]) > 100:
                    data[k] = data[k].strip()[0:100]
                buff[k] = data[k].strip() if isinstance(data[k], str) else data[k]
        return buff
    return False


def verify_mail(mail: str) -> bool:
    """
    verify mail whether invalid
    """
    return True if re.match("^.+\\@(\\[?)[a-zA-Z0-9\\-\\.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(\\]?)$", mail) else False


def verify_username(username: str) -> bool:
    return True if re.match("^[A-Z0-9a-z_\\-.]{6,10}$", username) else False


def verify_true_false(i) -> bool:
    """
    verify object(i) is true or false
    """
    return True if i in ('1', 1, 'true', 'false', 0, '0') else False
