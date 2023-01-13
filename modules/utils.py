def is_positive_int(n):
    return n.isdigit()


def convert_to_bool(bool_string: str):
    """
    Careful: True or False is valid. Check if is None to see if this conversion failed
    """
    if bool_string.lower() in ['false', 'no', 'off', 'disable']:
        return False
    elif bool_string.lower() in ['true', 'yes', 'on', 'enable']:
        return True
    return None


def add_a_or_an(string: str) -> str:
    """
    Add a or an to a string
    """
    if string[0].lower() in ['a', 'e', 'i', 'o', 'u']:
        return f'an {string}'
    return f'a {string}'
