from asyncore import read
import requests
import json
import pandas as pd
import numpy as np
import csv

class Objectify(object):
    """
    Creates a class with attributes and values from the provided key-value pairs 
    """    
    def __init__(self, **attrs):
        self.__dict__.update(attrs)

class OrangetheoryAPI:
    """
    Wrapper class for Orangetheory APIs.
    """

    def __init__(self, client_id=None, username=None, password=None):
        """
        Initializes the Orangetheory API class.

        Parameters
        ----------
        client_id : str
            The app's client_id
        username : str
            The username of the OTF user 
        password : str
            The password of the OTF user
        """
        self.OTF_AUTH_ENDPOINT = 'https://cognito-idp.us-east-1.amazonaws.com/'

        # Get OTF id_token and access_token
        headers = {
            'Content-Type': 'application/x-amz-json-1.1', 
            'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth'
        }
        body = {
            'AuthParameters': {
                'USERNAME': username, 
                'PASSWORD': password
            },
            'AuthFlow': 'USER_PASSWORD_AUTH', 
            'ClientId': client_id
        }
        response = requests.post(self.OTF_AUTH_ENDPOINT, headers=headers, json=body)
        response.raise_for_status()
        response_json = json.loads(response.content)
        self.id_token = response_json['AuthenticationResult']['IdToken']
        self.access_token = response_json['AuthenticationResult']['AccessToken']

    def member(self):
        """
        Returns an OTFMember object for this OTF user.
        """
        return OTFMember(self)

    def in_studio_workouts(self, csv_filename=''):
        """
        Returns an OTFInStudioWorkouts object for this OTF user.

        Parameters
        ----------
        csv_filename : string, optional 
            CSV file to load data from instead of connecting to Orangetheory. Great for debugging ;)
        """
        return OTFInStudioWorkouts(self, csv_filename)
        
    
class OTFMember:
    """
    Wrapper class for Orangetheory member API
    """

    def __init__(self, otf_api: OrangetheoryAPI):
        """
        Initializes the OTFMember class. 

        Parameters
        ----------
        otf_api : OrangetheoryAPI
        """
        # Get user data from OTF and objectify into UserAttributes
        headers = {
            'Content-Type': 'application/x-amz-json-1.1',
            'X-Amz-Target': 'AWSCognitoIdentityProviderService.GetUser'           
        }
        body = {
            'AccessToken': otf_api.access_token
        }
        response = requests.post(otf_api.OTF_AUTH_ENDPOINT, headers=headers, json=body)
        response.raise_for_status()
    
        # To convert the user attributes to an object, we create a dictionary of all attributes and values 
        user_attrs = {attr['Name']: attr['Value'] for attr in json.loads(response.content)['UserAttributes']}
        user_attrs['user_id'] = json.loads(response.content)['Username']

        # Then we clean dictionary key names because some of them contain invalid characters like ':'
        user_attrs_clean = dict((k.replace(':', '_'), v) for k, v in user_attrs.items())
        
        # Then convert the clean dictionary to an object 
        self.user_attributes = Objectify(**user_attrs_clean)

        # Get member data
        headers = {
            'Content-Type': 'application/json', 
            'Authorization': otf_api.id_token
        }
        self.OTF_MEMBER_ENDPOINT = 'https://api.orangetheory.co/member/members/'
        member_url = f"{self.OTF_MEMBER_ENDPOINT}{self.user_attributes.user_id}?include=memberClassSummary"
        response = requests.get(member_url, headers=headers)
        response.raise_for_status()
        
        # Objectify appropriately
        member_data = json.loads(response.content)['data']
        self.class_summary = Objectify(**member_data.pop('memberClassSummary'))
        self.home_studio = Objectify(**member_data.pop('homeStudio'))
        self.member_profile = Objectify(**member_data.pop('memberProfile'))
        self.member_data = Objectify(**member_data)


class OTFInStudioWorkouts:
    """
    Wrapper class for Orangetheory in-studio workout data 
    """

    def __init__(self, otf_api: OrangetheoryAPI, csv_filename: str = ''):
        """
        Initializes the OTFInStudioWorkoutsDF class. 

        Parameters
        ----------
        otf_api : OrangetheoryAPI
        csv_filename : string, optional 
            CSV file to load data from instead of connecting to Orangetheory. Great for debugging ;)
        """

        self.OTF_IN_STUDIO_ENDPOINT = 'https://api.orangetheory.co/virtual-class/in-studio-workouts'

        # Get class data from OTF or CSV if provided
        if csv_filename == '':
            headers = {
                'Content-Type': 'application/json', 
                'Authorization': otf_api.id_token
            }
            response = requests.get(self.OTF_IN_STUDIO_ENDPOINT, headers=headers)
            response.raise_for_status()
            self.data = json.loads(response.content)['data']
            self.dataframe = pd.DataFrame.from_records(
                data= self.data, 
                exclude=['classHistoryUuId', 'classId', 'isIntro', 'isLeader', 'memberEmail', 'memberName', 'memberPerformanceId', 'studioAccountUuId', 'version', 'workoutType']
            )
        else:
            self.dataframe = pd.read_csv(csv_filename)
            self.data = []
            with open(csv_filename, 'r') as csv_file:
                reader = csv.reader(csv_file)
                keys = next(reader)
                dict_item = {}
                for row in reader:
                    for i, value in enumerate(row):
                        if keys[i] == '':
                            key_name = 'key'
                        else:
                            key_name = keys[i]
                        dict_item[key_name] = value
                    self.data.append(dict_item)

    def by_coach(self, ascending=True, first_name_only=False) -> pd.DataFrame:
        """
        Returns data by coach name sorted by class count. 
        Specify ascending=False to show coaches with most classes first.
        Specify first_name_only=True to group coaches by their first name.
        """
        coach_data_df = self.dataframe.copy(deep=True)
        if first_name_only:
            coach_data_df["coach"] = coach_data_df["coach"].apply(lambda x: x.split(' ')[0].title())
        pivot = coach_data_df.pivot_table(
            index='coach',
            values='memberUuId',
            aggfunc=np.count_nonzero
        ).rename(columns={'memberUuId': 'class count'}).sort_values(by='class count', ascending=ascending)
        return pivot

    def by_studio(self, ascending=True) -> pd.DataFrame:
        """
        Returns data by studio name sorted by class count. 
        Specify ascending=False to show studios with most classes first.
        """
        pivot = self.dataframe.pivot_table(
            index='studioName',
            values='memberUuId',
            aggfunc=np.count_nonzero
        ).rename(columns={'memberUuId': 'class count'}).sort_values(by='class count', ascending=ascending)
        return pivot

    def by_class_type(self, ascending=True) -> pd.DataFrame:
        """
        Returns data by class type sorted by class count.
        Specify ascending=False to show class types with most classes first.
        """
        pivot = self.dataframe.pivot_table(
            index='classType',
            values='memberUuId',
            aggfunc=np.count_nonzero
        ).rename(columns={'memberUuId': 'class count'}).sort_values(by='class count', ascending=ascending)
        return pivot
        
