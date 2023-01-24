"""
Installing what it is necessary:
    pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib

Project:
    https://console.cloud.google.com/welcome?project=monitor-353019

On the side bar navigation go to
    1) "APIs and Services"
    2) "Enabled APIs and services" and enable Google Drive API
    3) go to Credentials and create OAuth 2.0 Client IDs
    4) download into the the working folder (E:\grains trading\Streamlit\Monitor) 
       client secret .json file (output of "OAuth client created") and rename it 'credentials.json'
    5) run the 'get_credentials' function and authenticate with google
    6) in the working folder (E:\grains trading\Streamlit\Monitor) a 'token.json' file has been created

Sources:
  Official Guide
    https://developers.google.com/drive/api/guides/about-sdk

    https://discuss.streamlit.io/t/google-drive-csv-file-link-to-pandas-dataframe/8057
    https://developers.google.com/drive/api/v2/reference/files/get

  Scope error:
    https://stackoverflow.com/questions/52135293/google-drive-api-the-user-has-not-granted-the-app-error

Files properties:
    https://developers.google.com/drive/api/v3/reference/files


Best part of all is the Query system to geet files and files information (check the function 'execute_query' and see where it is used).
High-level:
    1) with a query (giving some conditions), you can seach the whole drive and identify which file you want
       Ex: query = "name = 'last_update.csv'" (look for files whose name is 'last_update.csv')

    2) with a list of fields (asking for some outputs), I can get the info for the above selected files
       Ex: fields='files(id, name, mimeType, parents)' --> give id, name, Type, and folders in which the file is contained (parents)


Query Examples:
    https://developers.google.com/drive/api/guides/search-files#examples
"""

# import sys;
# sys.path.append(r'C:\Monitor\\')
# sys.path.append(r'\\ac-geneva-24\E\grains trading\Streamlit\Monitor\\')

import os
import os.path
from io import BytesIO
import pandas as pd
import pandas._libs.lib as lib
import concurrent.futures
import pickle

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload, MediaIoBaseUpload


def get_credentials() -> Credentials:
    # If modifying these scopes, delete the file token.json.
    # SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']
    SCOPES = ['https://www.googleapis.com/auth/drive']

    creds = None
    check_folders=[r'C:\Monitor\\', r'\\ac-geneva-24\E\grains trading\Streamlit\Monitor\\']
    token_file='token.json'
    for folder in check_folders:
        if os.path.exists(folder+'token.json'):
            token_file=folder+'token.json'
            print('Found:',token_file)
            break

    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds

def print_all_GDrive_files(max_n_files_to_print=1000):
    """
    I used it to see that files that GDrive sees
    because one time, it kept getting files already deleted that were in the trash

    import APIs.GDrive as gd
    gd.print_all_GDrive_files()    
    """        
    print_name_id(pageSize=max_n_files_to_print)


def print_name_id(creds: Credentials=None, pageSize: int=1000) -> None:
    if creds is None:
        creds=get_credentials()

    try:
        service = build('drive', 'v3', credentials=creds)

        # Call the Drive v3 API
        results = service.files().list(pageSize=pageSize, fields="nextPageToken, files(id, name)").execute()
        items = results.get('files', [])

        if not items:
            print('No files found.')
            return
            
        print('Files:')
        for item in items:
            print(u'{0} ({1})'.format(item['name'], item['id']))

    except HttpError as error:
        # TODO(developer) - Handle errors from drive API.
        print(f'An error occurred: {error}')

def execute_query(service, query = "name = 'last_update.csv'",fields='files(id, name, mimeType, parents)'):
    fo = []
    page_token = None
    while True:
        response = service.files().list(q=query,spaces='drive',fields='nextPageToken,'+fields,pageToken=page_token).execute()
        fo.extend(response.get('files', []))
        page_token = response.get('nextPageToken', None)

        if page_token is None:
            break
    return fo

def update_file_from_id(df, file_id,service=None,creds=None):
    if service is None:
        if creds is None:
            creds=get_credentials()
        service = build('drive', 'v3', credentials=creds, cache_discovery=False)

    fh =BytesIO(bytes(df.to_csv(),'ascii'))
    media_body=MediaIoBaseUpload(fh, mimetype='text/csv')
    
    updated_file = service.files().update(fileId=file_id, media_body=media_body).execute()
    print('Done update_file_from_id')

def save_in_folder(df,file_name='test.csv',folder='Data/Tests',service=None,creds=None):
    if service is None:
        if creds is None:
            creds=get_credentials()
        service = build('drive', 'v3', credentials=creds, cache_discovery=False)

    folder_id=get_file_id_from_path(file_path=folder,creds=creds,service=service)

    file_metadata = {
        'name': file_name,
        'parents':[folder_id]
        }

    fh =BytesIO(bytes(df.to_csv(),'ascii'))
    media_body=MediaIoBaseUpload(fh, mimetype='text/csv')

    file = service.files().create(body=file_metadata, media_body=media_body).execute()
    print('Saved',file_name)


def download_file_from_id(file_id,service=None,creds=None):
    if service is None:
        if creds is None:
            creds=get_credentials()
        service = build('drive', 'v3', credentials=creds, cache_discovery=False)

    request = service.files().get_media(fileId=file_id)
    file = BytesIO()
    downloader = MediaIoBaseDownload(file, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()

    file.seek(0)    
    return file

def get_file_id_from_path(file_path,creds=None,service=None):
    if service is None:
        if creds is None:
            creds=get_credentials()
        service = build('drive', 'v3', credentials=creds, cache_discovery=False)

    split = file_path.split('/')
    folders = split[0:-1]
    file_name = split[-1]

    fields='files(id, name, mimeType, parents)'

    files_query=query=f"name = '{file_name}'"
    files = execute_query(service=service, query=files_query, fields=fields)

    files_dict={}
    for f in files:
        files_dict[f['id']]={'name':f['name'],'id':f['id'],'parents':f['parents']}

    folders_query = "trashed = false and mimeType = 'application/vnd.google-apps.folder'"
    folders = execute_query(service=service, query=folders_query, fields=fields)

    folders_dict={}
    for f in folders:
        if 'parents' in f:
            folders_dict[f['id']]={'name':f['name'],'id':f['id'],'parents':f['parents']}

    dict_paths_id={}

    for f in files_dict:
        fo=[files_dict[f]['name']]
        dict_paths_id['/'.join(get_parent(id=files_dict[f]['parents'][0],folders_dict=folders_dict,fo=fo))]=f
            
    file_id= dict_paths_id[file_path]

    return file_id

def list_all_files_in_a_folder(folder='Data/Tests',service=None,creds=None):
    """
    Change:
        fields='files(id, name, parents, modifiedTime)'

    to get a different set of information
    """

    if service is None:
        if creds is None:
            creds=get_credentials()
    
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)

    folder_id=get_file_id_from_path(file_path=folder,creds=creds,service=service)
    print(folder_id)

    fields='files(id, name, parents, modifiedTime)'
    files_query=f"'{folder_id}' in parents"
    files = execute_query(service=service, query=files_query, fields=fields)

    files_dict={}
    for f in files:
        files_dict[f['id']]={'name':f['name'],'id':f['id'],'parents':f['parents'],'modifiedTime':f['modifiedTime']}

    return files_dict


def download_file_from_path(creds: Credentials, file_path):
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)

    split = file_path.split('/')
    folders = split[0:-1]
    file_name = split[-1]

    # Get file
    fields='files(id, name, mimeType, parents)'
    files_query=f"name = '{file_name}'"
    files = execute_query(service=service, query=files_query, fields=fields)

    files_dict={}
    for f in files:
        files_dict[f['id']]={'name':f['name'],'id':f['id'],'parents':f['parents']}

    # Get folder
    folders_query = "trashed = false and mimeType = 'application/vnd.google-apps.folder'"
    folders = execute_query(service=service, query=folders_query, fields=fields)

    folders_dict={}
    for f in folders:
        if 'parents' in f:
            folders_dict[f['id']]={'name':f['name'],'id':f['id'],'parents':f['parents']}

    dict_paths_id={}

    for f in files_dict:
        fo=[files_dict[f]['name']]
        dict_paths_id['/'.join(get_parent(id=files_dict[f]['parents'][0],folders_dict=folders_dict,fo=fo))]=f
            
    return download_file_from_id(service=service, file_id= dict_paths_id[file_path])


def get_parent(id,folders_dict,fo):
    if (id in folders_dict) and ('parents' in folders_dict[id]):
        fo.insert(0,folders_dict[id]['name'])
        get_parent(folders_dict[id]['parents'][0],folders_dict,fo)    
    return fo

def read_csv_parallel(donwload_dict,creds=None,max_workers=500):
    fo={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results={}
        for i,v in enumerate(donwload_dict['file_path']):
            file_path=donwload_dict['file_path'][i]
            dtype=donwload_dict['dtype'][i] if 'dtype' in donwload_dict else None
            parse_dates=donwload_dict['parse_dates'][i] if 'parse_dates' in donwload_dict else False
            index_col=donwload_dict['index_col'][i] if 'index_col' in donwload_dict else None
            names=donwload_dict['names'][i] if 'names' in donwload_dict else lib.no_default
            header=donwload_dict['header'][i] if 'header' in donwload_dict else 'infer'
            dayfirst=donwload_dict['dayfirst'][i] if 'dayfirst' in donwload_dict else False

            results[file_path] = executor.submit(read_csv, file_path, creds, dtype, parse_dates, index_col, names, header, dayfirst)
    
    for file_path, res in results.items():
        fo[file_path]=res.result()

    return fo

def read_csv(file_path, creds=None, dtype=None, parse_dates=False, index_col=None, names=lib.no_default, header='infer', dayfirst=False, comment=False, force_reading_from_GCloud = False):        
    if not os.path.exists(file_path) or force_reading_from_GCloud:
        if comment:
            print('Reading from GCloud:', file_path)
        if creds==None: creds = get_credentials()
        file_path=download_file_from_path(creds,file_path)        
    else:
        if comment:
            print('Reading from Local:', file_path)
        
    return pd.read_csv(file_path,dtype=dtype,parse_dates=parse_dates,index_col=index_col,names=names,header=header,dayfirst=dayfirst)


def uu_deserialize(file_path, comment=True):
    if comment:print('Start Deserializing:', file_path)
    obj= pickle.load(open(file_path, "rb"))
    if comment:print('Done Deserializing:', file_path)
    return obj

def deserialize(file_path, creds=None,comment=False):
    if not os.path.exists(file_path):
        if creds==None: creds = get_credentials()
        file=download_file_from_path(creds,file_path)
        return pickle.load(file)
    else:
        return uu_deserialize(file_path, comment)

if __name__ == "__main__":
    get_credentials()