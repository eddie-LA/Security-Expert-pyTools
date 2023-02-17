from ast import Try
from email.mime import image
from pickle import OBJ
import sys, os, subprocess
import fnmatch
import shutil
import pyodbc
import numpy as np
import pandas as pd
from datetime import datetime
import logging
from pathlib import Path
from consolemenu import ConsoleMenu, SelectionMenu
from consolemenu.items import FunctionItem, SubmenuItem, CommandItem
from sqlalchemy.engine import URL, create_engine
from modules import Alarms, Areas, Cameras, Controllers, Doors, DVRs, EventFilters,FloorPlans, FloorPlanSymbols, Intercoms, LineData, LinePointsData, PGMs, Sites, TroubleZones



# Connection information:
# You are likely to have 
server = '192.168.202.128'
database = 'SecurityExpert'

# If it fails, you may connect to the DB via username/passwd. Usually the username is 'sa' and the passwd is the one you entered in the installation.
# It may not have access to the SECURITYEXPERT databases though.
## You can also create a new user in SSMS and use that. (recommended)
username = 'external'
password = '1qaz2wsx'

# Here you can modify the backup directory name, if you like
dirname = f'backup_{datetime.utcnow().strftime("%d_%m_%Y_%H-%M-%S")}'

tables = ['Alarms','Areas', 'Cameras', 'Controllers', 'Doors', 'DVRs', 'EventFilters', 'ElevatorCars',
         'FloorPlans', 'FloorPlanSymbols', 'Intercoms', 'LineData', 'LinePointsData', 
         'PGMs', 'Roles', 'Variables', 'SaltoDoors', 'Sites', 'TroubleZones', 'Zones'
         ] # This should be the same as the modules import above. To extend this application, write a module named the same as the table you want and add the name here.

##

## ---------------------- DB Connection ----------------------
# Attempt local connection...
def Connect():
    connected = False;
    try:
        cnxn_string = ('DRIVER={ODBC Driver 18 for SQL Server};'
                        'SERVER='+server+';'
                        'DATABASE='+database+';'
                        'Trusted_Connection=yes;'
                        'TrustServerCertificate=Yes;'
                        )
        connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": cnxn_string})
        #connection_url = f'mssql+pyodbc://{server}/{database}?driver=ODBC+Driver+18+for+SQL+Server?Trusted_Connection=yes'
        #connection_url = URL.create(
        #    "mssql+pyodbc",
        #    host="192.168.202.128",
        #    port=1433,
        #    database="SecurityExpert",
        #    query={
        #        "driver": "ODBC Driver 18 for SQL Server",
        #        "TrustServerCertificate": "yes",
        #        "Trusted_Connection": "yes"
        #        },
        #    )

        engine = create_engine(connection_url)

        # Test connection 
        with engine.connect() as connection:
            sql_query = pd.read_sql(f'SELECT * FROM [SecurityExpert].[dbo].[Controllers];'
                                    ,connection)                            
        logging.info(f' Successfully connected to {database} using Windows credentials')
        connected = True
    except:
        logging.warning(' Local DB connection using Windows Credentials attempt failed. Trying to connect using a username/passwd...');


# In order to keep encryption, but without the need for a trusted root certificate (those cost money and are not necessary here), trust the server certificate
# You may use ODBC Driver 18 and 17 as well - https://learn.microsoft.com/en-us/sql/connect/odbc/windows/release-notes-odbc-sql-server-windows?view=sql-server-ver16
    if not connected:
        try:
            cnxn_string = ('DRIVER={ODBC Driver 18 for SQL Server};'
                            'SERVER='+server+';'
                            'DATABASE='+database+';'
                            'UID='+username+';'
                            'PWD='+password+';'
                            'TrustServerCertificate=Yes;'
                            )
            connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": cnxn_string})
            #connection_url = f'mssql+pyodbc://{username}:{password}@{server}/{database}?driver=ODBC+Driver+18+for+SQL+Server?TrustServerCertificate=Yes' 
            #connection_url = URL.create(
            #    "mssql+pyodbc",
            #    username="external",
            #    password="1qaz2wsx",
            #    host="192.168.202.128",
            #    port=1433,
            #    database="SecurityExpert",
            #    query={
            #        "driver": "ODBC Driver 18 for SQL Server",
            #        "TrustServerCertificate": "yes"
            #        },
            #    )
            engine = create_engine(connection_url)

            # Test connection 
            with engine.connect() as connection:
                sql_query = pd.read_sql(f'SELECT * FROM [SecurityExpert].[dbo].[Controllers];'
                                        ,connection)

            logging.info(f' Successfully connected to {database} using username/passwd')
        except:
            logging.warning(' Connection to DB using username/passwd failed. The program will now exit.')
            exit()
    return engine

## --------------------- Method declarations ---------------------
def CreateBackupDirPath():
    path = Path.cwd() / dirname
    try:
        path.mkdir(exist_ok = False)
    except FileExistsError:
        logging.warning(' Directory {dirname} already exists! Overwriting backup files...')

    return path
    

# Description: Writes a SQL table to a CSV file and puts it in a certain folder, depending on operation.
# Takes: cnxn - pyODBC connection, tableName, operation - 0 is working set, 1 is backup
# Returns: nothing
def WriteTableToFile(cnxn, tableName: str, operation: bool):
    with cnxn.connect() as connection:
        sql_query = pd.read_sql(f'SELECT * FROM [SecurityExpert].[dbo].[{tableName}];'
                                ,connection) # here, the 'conn' is the variable that contains your database connection information from step 2

    df = pd.DataFrame(sql_query)
    if operation: 
        # Take a backup with the dirname above (it is created at start of script!)
        path = Path() / dirname / f'{tableName}.csv'
    else: 
        # Use same method to create working set, avoids code duplication
        path = Path() / 'working_set' / f'{tableName}.csv'
    df.to_csv (path, index = False)


# Description: Restores the CSV bacup to a remote Security Expert DB.
# Takes: cnxn - pyODBC connection
# Returns: nothing / TODO: error msgs or exceptions
def RestoreAll(cnxn):
    # First, build a working set of the current environment
    for table in tables:
        WriteTableToFile(cnxn, table, 0)

    # Perform check if all files are present
    if not CheckCSV(): # TODO: move this check to wherever the user makes a folder selection
        logging.error('The selected folder does not have all the required backup files!')
        raise RuntimeError('Exiting...')

    # Fetch DFs in order - Controllers, Sites, FloorPlans, everything else... TODO: refactoring here according to above ^
    path = Path() / GetBackupDirsPath()[-1] # execute this once, then keep in memory
    sites = Sites()
    ctrlrs = Controllers()
    fps = FloorPlans()
    fpsymbols = FloorPlanSymbols()
    dvrs = DVRs()
    cams = Cameras()
    pgms = PGMs()
    intercoms = Intercoms()
    evfilters = EventFilters()
    alarms = Alarms()
    areas = Areas()
    tbzones = TroubleZones()
    ldata = LineData()
    lpdata = LinePointsData()
    

    # Run preprocess for all objects, ORDER IS IMPORTANT!
    temp_path = path / 'Sites.csv'  # depends on nothing
    sites.FetchAndPreprocess(cnxn, temp_path)
    sites.Restore(cnxn)

    # if there are Sites IDs to process | TODO: try to reduce coupling between objects, taken to separate method
    if sites.dictdf.empty:
        logging.debug(' No Sites to restore...')

    temp_path = path / 'Controllers.csv' # depends on Sites
    ctrlrs.FetchAndPreprocess(cnxn, temp_path)
    ctrlrs.ProcessIDs(sites.dictdf)
    ctrlrs.Restore(cnxn)

    if ctrlrs.dictdf.empty:
        logging.debug(' No Controllers to restore...')

    temp_path = path / 'FloorPlans.csv' # depends on Sites, (RecordGroup)
    fps.FetchAndPreprocess(cnxn, temp_path)
    fps.ProcessIDs(sites.dictdf)
    fps.Restore(cnxn)

    temp_path = path / 'FloorPlanSymbols.csv' # depends on nothing
    fpsymbols.FetchAndPreprocess(cnxn, temp_path)
    fpsymbols.ProcessIDs()
    fpsymbols.Restore(cnxn)

    if fps.dictdf.empty:
        logging.debug(' No FloorPlans to restore...')

    temp_path = path / 'DVRs.csv' # depends on Sites
    dvrs.FetchAndPreprocess(cnxn, temp_path)
    dvrs.ProcessIDs(sites.dictdf)
    dvrs.Restore(cnxn)

    temp_path = path / 'Cameras.csv' # depends on Sites, FloorPlans, DVRs
    cams.FetchAndPreprocess(cnxn, temp_path)
    cams.ProcessIDs(sites.dictdf, fps.dictdf, dvrs.dictdf)
    cams.Restore(cnxn)

    temp_path = path / 'PGMs.csv' # depends on Controllers, FloorPlans, Cameras
    pgms.FetchAndPreprocess(cnxn, temp_path)
    pgms.ProcessIDs(ctrlrs.dictdf, fps.dictdf, cams.dictdf)
    pgms.Restore(cnxn)

    temp_path = path / 'Intercoms.csv' # depends on Sites, FloorPlans, Cameras
    intercoms.FetchAndPreprocess(cnxn, temp_path)
    intercoms.ProcessIDs(sites.dictdf, fps.dictdf, cams.dictdf)
    intercoms.Restore(cnxn)

    temp_path = path / 'EventFilters.csv' # depends on Sites, FloorPlans
    evfilters.FetchAndPreprocess(cnxn, temp_path)
    evfilters.ProcessIDs(sites.dictdf, fps.dictdf)
    evfilters.Restore(cnxn)

    temp_path = path / 'Alarms.csv' # depends on Sites, FloorPlans, EventFilters
    alarms.FetchAndPreprocess(cnxn, temp_path)
    alarms.ProcessIDs(sites.dictdf, fps.dictdf, evfilters.dictdf)
    alarms.Restore(cnxn)

    temp_path = path / 'Areas.csv' # depends on Controllers, PGMs
    areas.FetchAndPreprocess(cnxn, temp_path)
    areas.ProcessIDs(ctrlrs.dictdf, pgms.dictdf)
    areas.Restore(cnxn)

    temp_path = path / 'TroubleZones.csv' # depends on Controllers, FloorPlans, Areas
    tbzones.FetchAndPreprocess(cnxn, temp_path)
    tbzones.ProcessIDs(ctrlrs.dictdf, fps.dictdf, areas.dictdf)
    tbzones.Restore(cnxn)


    temp_path = path / 'LineData.csv' # depends on FloorPlans, Doors, SaltoDoors, Areas, TroubleZones, PGMs (Outputs), Controllers, Elevators, Zones (Inputs), Cameras | works together with LinePointsData through LineID
    ldata.FetchAndPreprocess(cnxn, temp_path, fps.dictdf) # role of fps.dictdf: to restore any objects ONLY if belonging to a restorable FP
    ldata.ProcessIDs(ctrlrs.dictdf, fps.dictdf)
    ldata.Restore(cnxn)

    temp_path = path / 'LinePointsData.csv' # depends on FloorPlans, works together with LineData through LineID
    lpdata.FetchAndPreprocess(cnxn, temp_path, fps.dictdf) # same as above
    lpdata.ProcessIDs(fps.dictdf)
    lpdata.Restore(cnxn)


# Description: Backs up the remote SQL tables and 
# Takes: cnxn - SQL connection info
# Returns: nothing / TODO: maybe error msgs?
def BackupAll(cnxn):
    ## Create the backup folder
    #CreateBackupDirPath()
    ## Take a normal backup
    #for table in tables:
    #    WriteTableToFile(cnxn, table, 1)
    floorplans = FloorPlans()
    path = Path() / GetBackupDirsPath()[-1] / 'FloorPlans.csv'
    floorplans.Backup(cnxn, path)
    
    print(f' Successfully backed up X objects in folder {path.parent}')

def GetBackupDirsPath():
    dirs = {}
    i = 1
    for d in Path().iterdir():
        if d.is_dir() and fnmatch.fnmatch(d, 'backup_*'):
            dirs[i] = d
            i+=1
    #dirs.sort(key = os.path.getmtime)
    return dirs


# Description: Checks if all required CSVs can be located inside the required folder TODO: make path choosable here too
# Takes: nothing (eventually a path)
# Returns: True/False
def CheckCSV():
    path = Path() / GetBackupDirsPath()[-1] # TODO: here
    csv_fnames = []
    for f in path.iterdir():
        csv_fnames.append(f.stem)
    #logging.debug(csv_fnames.sort() == tables.sort())
    return csv_fnames.sort() == tables.sort() # Use sort to make abosultely sure the lists are in the same order! Perf penalty is negligible for already sorted lists.


## --------------    Restore (Simple) Methods      ---------------

# method that restores Sites from CSV to DB, matched by Name
dictdf_sites = pd.DataFrame
def RestoreSites(cnxn, dPath):
    global dictdf_sites
    path = dPath / 'Sites.csv'
    date_fields = ['DefaultUserStartDate','DefaultUserExpiryDate','OneTimeStartTime','StartingAt','StartingAt2','EndingAt','StartDate','EndDate','ExportLastRunTime','ExportNextRunTime','WirelessCredentialsLastSyncTime','LastModified','Created']

    with cnxn.begin() as conn:
        df = pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[Sites];'
                                ,con=conn
                                ,parse_dates=date_fields
                                ) # here, the 'conn' is the variable that contains your database connection information from step 2
        df3_db = df.copy() # copy so SQL data isn't touched
    try:
        df2 = pd.read_csv(path
                          ,sep=';'
                          ,parse_dates=date_fields
                          ,infer_datetime_format=True
                          )
        df3_csv = df2.copy() # create a copy to handle the opposite IDs
    except FileNotFoundError:
        logging.error(' Sites.CSV backup file was not found!!! Exiting...')
        return -1 # exit the method! we can't restore that which doesn't exist

    df2['is_equal'] = np.where(df2['Name'].isin(df['Name']), True, False)           # make a new col in df2 (the CSV) that compares the names of objects to df (the DB)
    df3_csv['is_equal'] = np.where(df3_csv['Name'].isin(df['Name']), True, False)   # gets similarities by Name from side of CSV (for the purposes of ID matching)
    df3_db['is_equal'] = np.where(df3_db['Name'].isin(df['Name']), True, False)     # gets similarities by Name from side of DB

    df2 = df2.loc[~df2['is_equal'], :] # copy-less removal of everything with attribute 'True' (we want the differences)
    df3_db = df3_db.loc[df3_db['is_equal'], :]  # create two more df's for the similarities
    df3_csv = df3_csv.loc[df3_csv['is_equal'], :] 

    df2 = df2.drop(columns='is_equal') # remove the now redundant 'is_equal 'column
    df3_db = df3_db.drop(columns='is_equal') 
    df3_csv = df3_csv.drop(columns='is_equal') 

    # for v2.0: maybe add a scanner that goes through the chose FPs and finds only which Sites and Controllers to add

    # First, add the similarities to the dictdf
    dictdf_sites = pd.DataFrame({'Name':df3_db['Name'],
                                 'Old': df3_csv['SiteID'],  # the old ID is the one in the backup
                                 'New': df3_db['SiteID']    # the new ID is the one in the DB
                                 })
    #print(dictdf_sites)
    # -------- for now, restore ALL possible Sites --------
    # if empty DF, do nothing, we have nothing to restore and it means dictdf is empty too
    if df2.empty:
        logging.debug(' The buffer dataframe is empty! There are no entries to restore. Exiting method...')
        return 0 # return type is up for... reconsideration, means nothing to restore

    # drop the rest, unfortunately it needs to be done row by row, so split the df in a df_list, we may want to keep having the tempdf though...
    df_list = [d for _, d in df2.groupby('SiteID')] 

    # Modify list in-place to remove NaNs and cols meant to be autofilled by the DB (identity and Rowversion/timestamp). Optimization: merge this with the next loop, may break stuff silently
    for index, df in enumerate(df_list):
        df_list[index] = (df_list[index].drop(columns=['SiteID'])
                                        .dropna(axis='columns')
        )
    # ------------------------------- probably cut method here, move to upper method and return df_list
    with cnxn.connect() as conn:
        for df in df_list:
            #print(df)
            df.to_sql('Sites', con=conn, if_exists='append', index=False)

    # ------------------------------------------------------------ probably cut method here and make a new one from code below - named Postprocess()
    df_list_names = df2['Name'].values

    # now we need to read what IDs the DB has given to the restored objects
    df_readback = pd.DataFrame()
    with cnxn.connect() as conn:
        for name in df_list_names:  # this loop may be able to be optimized and removed by using Name IN (?) and a stringified list, but for now that doesn't seem to work
            df_readback = pd.concat([df_readback,
                                pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[Sites] WHERE Name=(?);'
                                                    ,con=conn
                                                    ,parse_dates=date_fields
                                                    ,params=[name]
                                                    )
                                ]
                                ,ignore_index=True)
    #print('printing readback df')
    #print(df_readback)

    # make a dictdf for the differences after restoring them too
    dictdf_sites_diff = pd.DataFrame({'Name': df2['Name'],
                                      'Old': df2['SiteID'].values, 
                                      'New': df_readback['SiteID'].values
                                      })
    dictdf_sites = pd.concat([dictdf_sites, dictdf_sites_diff]) # concat the two tables, NEEDS THEM IN A LIST
    print(' DICT DF SITES set to:', dictdf_sites)

# method that restores Controllers from CSV to DB, matched by Name
dictdf_controllers = pd.DataFrame
def RestoreControllers(cnxn, dPath):
    global dictdf_controllers
    path = dPath / 'Controllers.csv'
    date_fields=['TestReport','AutomaticOfflineTime','LastDownloaded','LastModified','Created']

    with cnxn.begin() as conn:
        df = pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[Controllers];'
                                ,con=conn
                                ,parse_dates=date_fields
                                ) # here, the 'conn' is the variable that contains your database connection information from step 2
        df3_db = df.copy() # copy so SQL data isn't touched
    try:
        df2 = pd.read_csv(path
                          ,sep=';'
                          ,parse_dates=date_fields
                          ,infer_datetime_format=True
                          )
        df3_csv = df2.copy() # create a copy to handle the opposite IDs
    except FileNotFoundError:
        logging.error(' Controllers.CSV backup file was not found!!! Exiting...')
        return -1 # exit the method! we can't restore that which doesn't exist

    df2['is_equal'] = np.where(df2['Name'].isin(df['Name']), True, False)           # make a new col in df2 (the CSV) that compares the names of objects to df (the DB)
    df3_csv['is_equal'] = np.where(df3_csv['Name'].isin(df['Name']), True, False)   # gets similarities by Name from side of CSV (for the purposes of ID matching)
    df3_db['is_equal'] = np.where(df3_db['Name'].isin(df['Name']), True, False)     # gets similarities by Name from side of DB

    df2 = df2.loc[~df2['is_equal'], :] # copy-less removal of everything with attribute 'True' (we want the differences)
    df3_db = df3_db.loc[df3_db['is_equal'], :]  # create two more df's for the similarities
    df3_csv = df3_csv.loc[df3_csv['is_equal'], :] 

    df2 = df2.drop(columns='is_equal') # remove the now redundant 'is_equal 'column
    df3_db = df3_db.drop(columns='is_equal') 
    df3_csv = df3_csv.drop(columns='is_equal') 

    # for v2.0: maybe add a scanner that goes through the chose FPs and finds only which Sites and Controllers to add

    # First, add the similarities to the dictdf
    dictdf_controllers = pd.DataFrame({'Name':df3_db['Name'],
                                       'Old': df3_csv['ControllerID'],  # the old ID is the one in the backup
                                       'New': df3_db['ControllerID']    # the new ID is the one in the DB
                                       })

    # For all the differences, MAKE SURE TO UPDATE WITH APPROPRIATE CHANGES TO SiteID before restoring!!!
    if not dictdf_sites.empty:
           df2['SiteID'] = df2['SiteID'].replace(dictdf_sites['Old'].values, dictdf_sites['New'].values)

    # -------- for now, restore ALL possible Sites --------
    # if empty DF, do nothing, we have nothing to restore and it means dictdf is empty too
    if df2.empty:
        logging.debug(' The buffer dataframe is empty! There are no entries to restore. Exiting method...')
        return 0 # return type is up for... reconsideration, means nothing to restore

    # drop the rest, unfortunately it needs to be done row by row, so split the df in a df_list, we may want to keep having the tempdf though...
    df_list = [d for _, d in df2.groupby('ControllerID')]

    # Modify list in-place to remove NaNs and cols meant to be autofilled by the DB (identity and Rowversion/timestamp). Optimization: merge this with the next loop, may break stuff silently
    for index, df in enumerate(df_list):
        df_list[index] = (df_list[index].drop(columns=['ControllerID', 'Rowversion'])
                                        .dropna(axis='columns')
                                        )
    
    with cnxn.connect() as conn:
        for df in df_list:
            #print(df)
            df.to_sql('Controllers', con=conn, if_exists='append', index=False)

    
    df_list_names = df2['Name'].values

    # now we need to read what IDs the DB has given to the restored objects
    df_readback = pd.DataFrame()
    with cnxn.connect() as conn:
        for name in df_list_names:  # this loop may be able to be optimized and removed by using Name IN (?) and a stringified list, but for now that doesn't seem to work
            df_readback = pd.concat([df_readback,
                                     pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[Controllers] WHERE Name=(?);'
                                                       ,con=conn
                                                       ,parse_dates=date_fields
                                                       ,params=[name]
                                                       )
                                     ]
                                    ,ignore_index=True)
    #print('printing readback df')
    #print(df_readback)

    # make a dictdf for the differences after restoring them too
    dictdf_controllers_diff = pd.DataFrame({'Name': df2['Name'],
                                            'Old': df2['ControllerID'].values, 
                                            'New': df_readback['ControllerID'].values
                                            })
    dictdf_controllers = pd.concat([dictdf_controllers, dictdf_controllers_diff]) # concat the two tables
    

# method that restores FloorPlan IDs from CSV to DB
# takes: cnxn, dPath -  path to current dir, selection_list - a list of IDs provided by the menu
# returns: 
dictdf_fps = pd.DataFrame
def RestoreFloorPlans(cnxn, dPath, selection_list):
    global dictdf_fps
    date_fields = ['PostPrintDateTimeData','LastModified','Created']
    path = dPath / 'FloorPlans.csv'
    try:
        df2 = pd.read_csv(path
                          ,sep=';'
                          ,parse_dates=date_fields
                          ,infer_datetime_format=True
                          )
    except FileNotFoundError:
        logging.error(' FloorPlans.CSV backup file was not found!!! Exiting...')
        sys.exit()

    df2.index += 1   # correct IDs from console UI to pandas
    df2 = df2.loc[selection_list] # select rows based on passed list

    #print(df2)
    #print(selection_list)

    # Get info for any changes in SiteIDs and apply any differences here | TODO: handle orphaned data?
    if not dictdf_sites.empty:
        print(df2)
        df2['SiteID'] = df2['SiteID'].replace(dictdf_sites['Old'].values, dictdf_sites['New'].values)

    # Solve RecordGroups by zeroing all of them, which have a value | TODO: May be better to just set them all to 'no value' (2147483647)
    df2['RecordGroup'] = 2147483647

    # Restore images (ONLY FOR ONES EXISTING IN CURRENT FOLDER)
    for image_path, row_name in zip(df2['BackgroundImage'], df2['Name']):
        if image_path:                                                  # check if path is empty, no need to work with empties
            path = dPath.parent / f'{row_name}.jpg'                     # make the path var
            image_path = path.__str__                                   # convert to string and set

    with cnxn.begin() as conn:
        df_db = pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[FloorPlans];'
                               ,con=conn
                               ,parse_dates=date_fields
                               )

    # Split the DF to a listin order to be able to process row-by-row
    df_list = [d for _, d in df2.groupby('FloorPlanID')] 

    # Modify list in-place to remove NaNs and cols meant to be autofilled by the DB (identity and Rowversion/timestamp). Optimization: merge this with the next loop, may break stuff silently
    for index, df in enumerate(df_list):
        df_list[index] = (df_list[index].drop(columns=['FloorPlanID'])
                                        .dropna(axis='columns')
        )

    df_list_names = df2['Name'].values

    # Push row by row list to DB, if it already exists, skip it and remove its name from the list, so its not included in df_readback later
    with cnxn.connect() as conn:
        for row in df_list:
            #print(df)
            if row['Name'].values in df_db['Name'].values:
                logging.info(f' FloorPlan named {row.Name.values} already exists! Skipping...')
                df_list_names.remove(row['Name'].values)
                continue
            row.to_sql('FloorPlans', con=conn, if_exists='append', index=False)

    

    # now we need to read what IDs the DB has given to the restored objects
    df_readback = pd.DataFrame()
    with cnxn.connect() as conn:
        for name in df_list_names:  # this loop may be able to be optimized and removed by using Name IN (?) and a stringified list, but for now that doesn't seem to work
            df_readback = pd.concat([df_readback,
                                     pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[FloorPlans] WHERE Name=(?);'
                                                       ,con=conn
                                                       ,parse_dates=date_fields
                                                       ,params=[name]
                                                       )
                                     ]
                                    ,ignore_index=True)
    #print('printing readback df')
    #print(df_readback)
    print('-- RESTORE FLOOR PLANS')
    print(df2)
    print(df_readback)
    if not df_readback.empty:
        dictdf_fps  = pd.DataFrame({'Old': df2['FloorPlanID'].values, 
                                    'New': df_readback['FloorPlanID'].values
                                    })
    print(' -- DICT DF Fps', dictdf_fps)


# method that backs up selected FloorPlans, LineData (these 2 have image fields) and objects from DB to CSV
# takes: cnxn, dPath -  path to current dir, selection_list - a list of IDs provided by the menu
# returns: list of FloorPlan IDs backed up
def BackupFloorPlans(cnxn, dPath: Path): # , selection_list):
    for table in tables:
        path = dPath / f'{table}.csv'

        if table == 'FloorPlans':
            date_fields = ['PostPrintDateTimeData','LastModified','Created']
            with cnxn.begin() as conn:
                df_fp = pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[{table}];'
                                          ,con=conn
                                          ,parse_dates=date_fields
                                          )
            # make it work with indices too
            #df_fp.index += 1   # correct IDs from console UI to pandas
            # df_fp = df_fp.loc[selection_list] # select rows based on passed list - JUST BACKUP ALL!

            # Backup images to the same folder with names = sanitized name of FloorPlan
            for image_path, row_name in zip(df_fp['BackgroundImage'], df_fp['Name']):
                if image_path:                                              # check if path is empty, no need to work with empties
                    src_path = Path(image_path)
                    img_name = "".join(x for x in row_name if x.isalnum())  # sanitize image for filename creation, turn into alphanumeric str
                    dest_path = dPath.parent / f'{img_name}.jpg'
                    try:
                        shutil.copy2(src=src_path, dst=dest_path) # attempt to copy the images and their metadata, ONLY WORKS WHEN SCRIPT IS RUN LOCALLY (same machine as images)
                    except FileNotFoundError as e:  # print out an error if images are not found!
                        print(e)
                
            df_fp.to_csv(path, sep=';', index = False)

        elif table == 'LineData':
            with cnxn.begin() as conn:
                df = pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[{table}];'
                                        ,con=conn
                )

            # Backup images to the same folder with names = sanitized name of object
            for image_path, row_name in zip(df['ImagePath'], df['Name']):
                if image_path:                                              # check if path is empty, no need to work with empties
                    src_path = Path(image_path)
                    img_name = "".join(x for x in row_name if x.isalnum())  # sanitize image for filename creation, turn into alphanumeric str
                    dest_path = dPath.parent / f'{img_name}.jpg'
                    try:
                        shutil.copy2(src=src_path, dst=dest_path) # attempt to copy the images and their metadata, ONLY WORKS WHEN SCRIPT IS RUN LOCALLY (same machine as images)
                    except FileNotFoundError as e:  # print out an error if images are not found!
                        print(e)

            #df = df.loc[df['FloorPlanID'].isin(ids_list)]  # keep only values from selected Floor Plans - JUST BACKUP ALL!
            df.to_csv(path, sep=';', index = False)
        else:
            with cnxn.begin() as conn:
                df = pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[{table}];'
                                       ,con=conn
                                       ) # here, the 'conn' is the variable that contains your database connection information from step 2

                # Take a backup with the dirname above (it is created at start of script!)
            df.to_csv (path, sep=';', index = False)

    return df_fp['FloorPlanID'].values    # return IDs


# method that runs processing on LineData, needs to be ran before restoring
# - accompanied by two dict structures representing the DB structure
# takes: cnxn, dPath - dir path of backup folder, ids_list - list of FP IDs to filter by
# returns: 
device_types = {    # holds DeviceTypeID (from LineData): table_name
        1: 'Doors'
        ,2: 'Areas'
        ,3: 'PGMs' #
        ,4: 'Zones' #
        ,5: 'TroubleZones' #
        ,6: 'ElevatorCars'
        ,7: 'Variables'
        ,100: 'SaltoDoors'
        ,1000: 'Cameras'
        }

deviceid_col_names = { # holds table_name: ID col
        'Doors': 'DoorID'
        ,'Areas': 'AreaID'
        ,'PGMs': 'PGMID' #
        ,'Zones': 'ZoneID' #
        ,'TroubleZones': 'TroubleZoneID' #
        ,'ElevatorCars': 'ElevatorCarID'
        ,'Variables': 'VariableID'
        ,'SaltoDoors': 'SaltoDoorID'
        ,'Cameras': 'CameraID'
        }

def ProcessLineData(cnxn, dPath: Path, ids_list: list):
    path = dPath / 'LineData.csv'   # read LineData
    try:
        df2 = pd.read_csv(path
                          ,sep=';'
                          )
    except FileNotFoundError:
        logging.error(' LineData.CSV backup file was not found!!! Exiting...')
        sys.exit()

    df2 = df2.loc[df2['FloorPlanID'].isin(ids_list)]  # keep only values from selected Floor Plans

    #df_list = [d for _, d in df2.groupby('ID')]     # split df into rows, need to process every item individually

    # Iterate over the list of rows 
    #for index, df in enumerate(df_list):
    #    df_list[index] = (df_list[index].drop(columns=['ID'])
    #                                    .dropna(axis='columns')
    #    )
    print(df2)
    #df2 = df2.reset_index(drop=True)   # not necessary
    to_remove = []  # list to hold IDs that need to be removed because custom fields in card templates will NOT be restored!
    to_remove_pointsdata = {}   # dict to hold k/v pairs of items that need to be removed from LinePointsData

    if not dictdf_fps.empty:            # correct the FloorPlanIDs from dictdf | the FloorPlans table *MUST* be restored properly! | keep only values from restorable FPs !!
        df2 = df2.loc[df2['FloorPlanID'].isin(dictdf_fps['Old'])]  
        df2['FloorPlanID'] = df2['FloorPlanID'].replace(dictdf_fps['Old'].values, dictdf_fps['New'].values)
        print('=== LINE DATA dict df ',  df2)

    else: # this should really not be empty
        sys.exit(' No restorable Floor Plans found. Exiting...')

    if not dictdf_controllers.empty:    # correct the DeviceControllerIDs from dictdf | the Controllers table *MUST* be restored properly!
        df2['DeviceControllerID'] = df2['DeviceControllerID'].replace(dictdf_controllers['Old'].values, dictdf_controllers['New'].values)

    # Process row by row
    for i in df2.index:
        #print(f'Current LineData row is {i}: ')
        #print(df2.loc[i])
        
        # row is about an object
        if df2['DeviceTypeID'].loc[i] in device_types.keys():  
            df2.loc[i] = CrawlTable(cnxn=cnxn, dPath=dPath, row=df2.loc[i])     # replace row with the correct info 

        # row is about an image
        elif not df2['ImagePath'].loc[i] == '': 
            obj_name = "".join(x for x in df2['Name'].loc[i] if x.isalnum())    # sanitize object name, this is the way images are backed up
            img_path = dPath.parent / f'{obj_name}.jpg'                         # make the path var lead to the image

            if img_path.exists():
                df2['ImagePath'].loc[i] = img_path.absolute().__str__           # convert to string and set new path
            else:
                logging.warning(f' Image {img_path} NOT FOUND! Please check manually if it exists and report the error!')
            
        # row is about a custom card template field 
        elif df2['Text'].loc[i] != None and ('<CUSTOM' in df2['Text'].loc[i] or '<CREDENTIALTYPEID' in df2['Text'].loc[i]):
            to_remove.append(i)                                                 # collect indices in list to drop later, DON'T DROP DURING LOOP!
            to_remove_pointsdata['FloorPlanID'].append( df2['LineID'].loc[i] )

    df2.drop(to_remove)                                                         # drop indices pertaining to custom fields 
    ProcessLinePointsData(cnxn, dPath, to_remove=to_remove_pointsdata)          # <-- LinePointsData is restored here
    
    # Split the DF to a listin order to be able to process row-by-row
    df_list = [d for _, d in df2.groupby('ID')] 

    # Modify list in-place to remove NaNs and cols meant to be autofilled by the DB (identity and Rowversion/timestamp). Optimization: merge this with the next loop, may break stuff silently
    for index, df in enumerate(df_list):
        df_list[index] = (df_list[index].drop(columns=['ID'])
                                        .dropna(axis='columns')
        )

    # Push row by row list to DB, if it already exists, skip it and remove its name from the list, so its not included in df_readback later
    print('Sending LineData to DB: ')
    with cnxn.connect() as conn:
        for row in df_list:
            row.to_sql('LineData', con=conn, if_exists='append', index=False)
    

           
# method that crawls object tables based on the device_types dict, restores an object to its respective table if it has to and returns updated row inormation for LineData
# - changes may only be made to 'DeviceControllerID' and 'DeviceAddressID'
# takes: cnxn, dPath - the dir path of the backup folder, row - a pd.Series entry representing the current row being processed
# returns: updated row
# - results in: FloorPlan objects being updated
def CrawlTable(cnxn, dPath: Path, row: pd.Series):
    row_copy = row.copy()
    table_name = device_types.get( row['DeviceTypeID'] )    # get table name from dict
    path = dPath / f'{table_name}.csv'                      # get path for local CSV based on table_name

    with cnxn.begin() as conn:  # read DB table
        df = pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[{table_name}];'
                                ,con=conn
        )
    
    try:                        # read CSV
        df2 = pd.read_csv(path
                          ,sep=';'
                          #,parse_dates=date_fields
                          ,infer_datetime_format=True
                          )
    except FileNotFoundError:
        logging.error(f' {table_name}.CSV backup file was not found!!! Exiting...')
        sys.exit()

    # look for object name in CSV table
    
    #print(df2[ deviceid_col_names.get(table_name) ])
    
    table_row_csv = df2[df2[ deviceid_col_names.get(table_name) ] == row_copy['DeviceAddressID'] ].copy()   # get the correct row from the CSV DF's ID index (saved in dict)
    #if table_name == 'Cameras' or table_name == 'Variables':
    #    print('-- Table name: ', table_name, ' device address id: ',row_copy['DeviceAddressID'])
    #    print('-- Last table_row_csv: ', table_row_csv)
    #    #print(' and table_row_csv Name: ', table_row_csv['Name']) # <--- issue here - this should be a pd.Series but is int ???

    #    print('-- DB df ', df)
    #    print('-- row [device addr id] ', row_copy['DeviceAddressID'])
    #    print('-- table row csv current name', table_row_csv['Name'].get( row_copy['DeviceAddressID'])) # <- this was the culprit, need exact string match, this messes it up if ID isnt same!
    #    #print('-- table row csv loc device addr id ',table_row_csv.loc['DeviceAddressID'])
    #    print(' ------ df name', df['Name'])
    #    print('------ table row csv name', table_row_csv['Name'])
    table_row_db = df[df['Name'] == table_row_csv['Name'].iat[0] ]  # get the same named row from DB, if it exists | iat[0] so string can be reached, otherwise it would NOT be fine to use if it wasn't only 1 entry
    #if table_name == 'Cameras' or table_name == 'Variables':
    #    print('-- table row db ', table_row_db)
    
    # modify the datetime to now so we know when object was restored
    curr_time = datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S")
    table_row_csv['Created'].iat[0] = pd.to_datetime(curr_time)
    table_row_csv['LastModified'].iat[0] = pd.to_datetime(curr_time)

    # if not empty, Name has been found in DB DF | get its ID and update row
    if not table_row_db.empty: 
        row_copy.loc['DeviceAddressID'] = table_row_db[ deviceid_col_names.get(table_name) ] # get ID col name from dict

    # if empty, Name has *NOT* been found in DB DF | restore table_row_csv object and get back its ID
    else:
        # treat PGMs, Zones and TroubleZones like the special kids they are, Doors too
        if table_name == 'PGMs':
            if not dictdf_controllers.empty:
                table_row_csv['ControllerID'] = table_row_csv['ControllerID'].replace(dictdf_controllers['Old'].values, dictdf_controllers['New'].values)
                table_row_csv['HostControllerRef'] = table_row_csv['HostControllerRef'].replace(dictdf_controllers['Old'].values, dictdf_controllers['New'].values)
            table_row_csv = table_row_csv[ ['Name', 'Name2', 'ControllerID', 'ReportingID', 'Module', 'ModuleAddress', 'ModuleOutput', 'HostControllerRef', 'LastModified', 'LastModifiedValid', 'Created'] ]   # keep only cols with *necessary* info

        elif table_name == 'Zones':
            if not dictdf_controllers.empty:
                table_row_csv['ControllerID'] = table_row_csv['ControllerID'].replace(dictdf_controllers['Old'].values, dictdf_controllers['New'].values)
                table_row_csv['HostControllerRef'] = table_row_csv['HostControllerRef'].replace(dictdf_controllers['Old'].values, dictdf_controllers['New'].values)
            table_row_csv = table_row_csv[ ['Name', 'Name2', 'ControllerID', 'ReportingID', 'Module', 'ModuleAddress', 'ModuleZone', 'HostControllerRef'] ]

        elif table_name == 'TroubleZones':
            if not dictdf_controllers.empty:
                table_row_csv['ControllerID'] = table_row_csv['ControllerID'].replace(dictdf_controllers['Old'].values, dictdf_controllers['New'].values)
                table_row_csv['HostControllerRef'] = table_row_csv['HostControllerRef'].replace(dictdf_controllers['Old'].values, dictdf_controllers['New'].values)
            table_row_csv = table_row_csv[ ['Name', 'Name2', 'ControllerID', 'TroubleGroup', 'TroubleGroupOptions', 'ReportingID', 'Module', 'ModuleAddress', 'ModuleZone', 'HostControllerRef', 'LastModified', 'LastModifiedValid', 'Created'] ]

        elif table_name == 'Doors':
            if not dictdf_controllers.empty:
                table_row_csv['ControllerID'] = table_row_csv['ControllerID'].replace(dictdf_controllers['Old'].values, dictdf_controllers['New'].values)
                table_row_csv['HostControllerRef'] = table_row_csv['HostControllerRef'].replace(dictdf_controllers['Old'].values, dictdf_controllers['New'].values)
            table_row_csv = table_row_csv[ ['Name', 'Name2', 'ControllerID', 'HostControllerRef', 'LastModified', 'LastModifiedValid', 'Created'] ]

        else: 
            if 'SiteID' in table_row_csv.columns:   # if object depends on Sites
                if not dictdf_sites.empty:
                    table_row_csv['SiteID'] = table_row_csv['SiteID'].replace(dictdf_sites['Old'].values, dictdf_sites['New'].values)

                table_row_csv = table_row_csv[ ['Name', 'Name2', 'SiteID', 'LastModified', 'LastModifiedValid', 'Created'] ] # keep only cols with basic info

            elif 'ControllerID' in table_row_csv.columns:   # if object depends on Controllers
                if not dictdf_controllers.empty:
                    table_row_csv['ControllerID'] = table_row_csv['ControllerID'].replace(dictdf_controllers['Old'].values, dictdf_controllers['New'].values)

                table_row_csv = table_row_csv[ ['Name', 'Name2', 'ControllerID', 'LastModified', 'LastModifiedValid', 'Created'] ]


        with cnxn.connect() as conn:
            print(f'-- Sending object in {table_name} to DB: ')
            print(table_row_csv)
            table_row_csv.to_sql(table_name, con=conn, if_exists='append', index=False) # <--- RESTORE object to respective table in DB

    # now read the object back and fetch its ID
    with cnxn.connect() as conn:
        df_readback = pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[{table_name}] WHERE Name=(?);'
                                        ,con=conn
                                        #,parse_dates=date_fields
                                        ,params=[ table_row_csv['Name'] ]
                                        )

    # update LineData ID based on readback value, using table ID col name dict
    row_copy.loc['DeviceAddressID'] = df_readback[ deviceid_col_names.get(table_name) ].iat[0]
    #print('--row ', row_copy)
    return pd.Series(row_copy, dtype=object)

# method that takes a list of data from ProcessLineData() in order to process and restore LinePointsData from CSV to DB
# takes: cnxn, dPath - dir path to backup folder, to_remove - dict with k/v pairs of FloorPlanID/LineIDs
# 
def ProcessLinePointsData(cnxn, dPath: Path, to_remove: dict):
    path = dPath / 'LinePointsData.csv'
    try:
        df2 = pd.read_csv(path
                          ,sep=';'
                          )
    except FileNotFoundError:
        logging.error(' LinePointsData.CSV backup file was not found!!! Exiting...')
        sys.exit()

    # update the FloorPlanIDs from dictdf to reach parity with LineData and get ready to restore
    # keep only restorables, otherwise the table gets full of duplicate data | if anything is restored it will be found in dictdf_fps
    if not dictdf_fps.empty:    
        df2 = df2.loc[df2['FloorPlanID'].isin(dictdf_fps['Old'])] 
        df2['FloorPlanID'] = df2['FloorPlanID'].replace(dictdf_fps['Old'].values, dictdf_fps['New'].values)
        #print('=== LINE PTS DATA dict df ',  df2['FloorPlanID'])

    # we need the dictdf to NOT be empty in order to restore
    else:
        sys.exit(' No restorable floor plans exist')

    for fp_id, line_ids in to_remove.items():
       # df2 = df2.drop([(df2['FloorPlanID'] == fp_id) & (df2['LineID'] == line_id) ].index) # drop rows where 
       df2 = df2[ ~(df2['FloorPlanID'].isin(fp_id) and df2['LineID'].isin(line_ids)) ] # remove rows where FloorPlanID and LineID are in the to_remove dict

    # drop the ID col
    df2 = df2.drop(columns=['ID'])

    # restore LinePointsData now that everything about it is fixed
    with cnxn.connect() as conn:
        print('Sending LinePointsData to DB: ')
        print(df2)
        df2.to_sql('LinePointsData', con=conn, if_exists='append', index=False)


# method that finds FloorPlan names from the CSV
# takes: dPath - path to backup dir
# returns: a dict of FP names
def ReadFPNames(dPath):
    path = dPath / 'FloorPlans.csv'
    try:
        df2 = pd.read_csv(path
                          ,sep=';'
                          #,parse_dates=date_fields
                          ,infer_datetime_format=True
                          )
    except FileNotFoundError:
        logging.error(' FloorPlans.CSV backup file was not found!!! Exiting...')
        sys.exit()

    df2.index += 1 # make DF index start from 1
    return df2['Name'].to_dict() # return a dict of the names of the FPs

## ------------------------     Menu      ------------------------
def menu_backup(cnxn):
    print('\n Starting backup process...')
    # do FULL BACKUP with progress bar / statements
    dPath = CreateBackupDirPath()
    BackupFloorPlans(cnxn, dPath)
    # TODO: backup FPs correctly!

def menu_restore_partial(cnxn):
    print('\n Choose a folder to restore from:')
    print(' The format of the folder name is backup_DD_MM_YY_HH_MM_SS.\n')
    dirs = GetBackupDirsPath()

    for i, dirname in dirs.items():
        print(f'  {i}. {dirname}')
    print(' ')

    option = menu_select(dirs)
    dPath = dirs[option] # get path of dir that user wants, this is the way (path)
    
    selection = fp_selection_menu(dPath)    # get indices of FloorPlans to restore

    # a method that finds which controllers and sites are used depending on objects

    # ------ Restore the main objects everything depends on ------
    RestoreSites(cnxn, dPath)       # always first
    RestoreControllers(cnxn, dPath) # depends on dictdf_sites

    print(' DICT DF SITES set to:', dictdf_sites)
    print(' DICT DF CTRLS set to:', dictdf_controllers)

    RestoreFloorPlans(cnxn, dPath, selection)
    ProcessLineData(cnxn, dPath, selection)
    
    # do FULL restore method with progress bar / statements

def menu_restore_full(cnxn):
    print('\n Choose a folder to restore from:')
    print(' The format of the folder name is backup_DD_MM_YY_HH_MM_SS.\n')
    dirs = GetBackupDirsPath()
    print(dirs)
    for i, dirname in dirs.items():
        print(f'  {i}. {dirname}')
    
    # call method that lets user choose which FPs to restore!
    
    # do PARTIAL restore method with progress bar / statements
    print('Full Restore is not implemented yet. ETA: v1.2-1.3')


def menu_select(collection):
    option = ''
    try:
        option = int(input('Enter your choice: '))
        if(not isinstance(option, int) and int(option) < 1 and int(option) > len(collection)+1):
            option = int(input('Enter your choice: '))
    except: 
        print('\nWrong input. Please enter a number from the list ...\n')
    while(not isinstance(option, int) and int(option) < 0 and int(option) > len(collection)+1):
        try:
            option = int(input('Enter your choice: '))
        except:
            print('\nWrong input. Please enter a number from the list ...\n')

    return option

# this method is the FloorPlan selection menu
# takes: dPath - path to backup folder
# returns: list containing indices for floor plans to restore
def fp_selection_menu(dPath):
    # ------ Ask which floorplans the user wants to restore ------
    fpnames = ReadFPNames(dPath)

    # set up our selection variables
    options = ''
    option_list = []

    if not bool(fpnames): # check if names dict is empty
        logging.warning(' No FloorPlans found in CSV! Check if file is present or corrupted... Exiting...')
        sys.exit('')

    while (True):
        try:
            # clear_console()
            print('\n Choose which Floor Plans to restore:')
            for i, fpname in fpnames.items():
                if i in option_list:    # if selected, star the row, also list index starts from 0, so fix that up 
                    print(f'  (*) {i}. {fpname}')
                else:
                    print(f'  {i}. {fpname}')
            print(f'   d. Done with selection\n')

            options = input('Enter your choices (separated by a comma or using a dash, e.g 1,3-6,8), then \'d\' when done: ')

            if options == 'd' and not len(option_list) == 0: # if we are d = Done and have some selection
                #print(option_list)
                return option_list
            else:
                print(options)
                option_list = parse(options) # if not done, parse options list
                option_list[:] = [o for o in option_list if o <= len(fpnames) and o > 0]    # recreate options list as safe if any values over or under were entered
        except: 
            print('\nWrong input. Please enter numbers from the list, separated with commas or dashes, then \'d\' when done: ...\n')




# this method parses a string with dashes and commas into a full ordered list of numbers  
def parse(num_str):
    num = []
    for part in num_str.split(','):
        p1 = part.split('-')
        if len(p1) == 1:
            num.append(int(p1[0]))
        else:
            num.extend(set(range(int(p1[0]), int(p1[1])+1)))
    return list(set(num)) # return unique values, just in case

def clear_console(): 
    os.system('cls')

## ------------------------     Main      ------------------------
def main():
    logging.Logger.setLevel(logging.getLogger(), level='DEBUG')
    #print(logging.getLogger().getEffectiveLevel())

    print ('Reading data from table')   # define connection (for pandas) and cursor (for pyODBC)
    cnxn = Connect()
    #cursor = cnxn.cursor()
    #SetupWorkingSetDir()

    while(True):
            print(
                '\nWelcome to SE SecurityExpert pyTools! Please select an acton from the menu:\n'
                ' 1: Backup\n'
                ' 2: Full Restore\n'
                ' 3: Partial Restore\n'
                ' 4: Exit\n'
                )
            option = ''
            try:
                option = int(input('Enter your choice: '))
            except:
                print('\nWrong input. Please enter a number ...\n')

            if option == 1:
               subprocess.run('cls', shell=True)
               menu_backup(cnxn)
               #progress bar? or printing progress statements
               break
            elif option == 2:
                menu_restore_full(cnxn)
                #progress bar?
                break
            elif option == 3:
                menu_restore_partial(cnxn)
                #progress bar?
                break
            elif option == 4:
                print('Thank you for using my software!')
                exit()
            else:
                if isinstance(option, int):
                    os.system('cls')  # this doesnt work in DEBUG, but works in RELEASE
                    print('Invalid option. Please enter a number between 1 and 4.\n')

if __name__ == '__main__':
    main()
    