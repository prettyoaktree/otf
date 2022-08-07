"""
Create a config.py file and specify OTF_CLIENT_ID, EMAIL, and PASSWORD
"""
import config
from orangetheory_api import OrangetheoryAPI

################
# MAIN PROGRAM #
################

print('Getting data from OTF...')
otf = OrangetheoryAPI(config.OTF_CLIENT_ID, config.EMAIL, config.PASSWORD)
member = otf.member()
print('Class Summary')
print('=============')
for k,v in vars(member.class_summary).items():
    print(f"{k}: {v}")
print()
print('Getting in-studio workout data...')
class_summary = otf.in_studio_workouts()
print()
print('All Details')
print('===========')
print(class_summary.dataframe)
print()
print('Number of Classes by Coach')
print('==========================')
print(class_summary.by_coach(ascending=False, first_name_only=True))
print()
print('Number of Classes by Studio')
print('===========================')
print(class_summary.by_studio(ascending=False))
print()
print('Number of Classes by Type')
print('=========================')
print(class_summary.by_class_type(ascending=False))
