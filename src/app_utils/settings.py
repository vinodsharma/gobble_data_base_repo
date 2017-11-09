import os
from os.path import join, dirname
from dotenv import load_dotenv


path = join(dirname(__file__), '.env')
load_dotenv(path)

logdna_key = os.getenv('LOGDNA_KEY')
logdna_app = os.getenv('LOGDNA_APP')
bugsnag_key = os.getenv('BUGSNAG_KEY')
bugsnag_release_stage = os.getenv('BUGSNAG_RELEASE_STAGE')
aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')


def get_settings_dict():
    settings_dict = {}
    settings_dict['LOGDNA_KEY'] = logdna_key
    settings_dict['LOGDNA_APP'] = logdna_app
    settings_dict['BUGSNAG_KEY'] = bugsnag_key
    settings_dict['BUGSNAG_RELEASE_STAGE'] = bugsnag_release_stage
    settings_dict['AWS_ACCESS_KEY_ID'] = aws_access_key_id
    settings_dict['AWS_SECRET_ACCESS_KEY'] = aws_secret_access_key
    return settings_dict
