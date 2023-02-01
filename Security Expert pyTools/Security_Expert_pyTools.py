import os
import fnmatch
import shutil
from sqlite3 import connect
import pyodbc
import numpy as np
import pandas as pd
from datetime import datetime
import logging
from pathlib import Path
from consolemenu import *
from consolemenu.items  import *
from sqlalchemy.engine import URL, create_engine
from modules import Alarms, Areas, Cameras, Controllers, Doors, EventFilters,FloorPlans, FloorPlanSymbols, Intercoms, LineData, LinePointsData, PGMs, Sites, TroubleZones

# Connection information:
# You are likely to have 
server = '192.168.202.128'
database = 'SECURITYEXPERT'

# If it fails, you may connect to the DB via username/passwd. Usually the username is 'sa' and the passwd is the one you entered in the installation.
# It may not have access to the SECURITYEXPERT databases though.
## You can also create a new user in SSMS and use that. (recommended)
username = 'external'
password = '1qaz2wsx'

# Here you can modify the backup directory name, if you like
dirname = f'backup_{datetime.utcnow().strftime("%d_%m_%Y_%H-%M-%S")}'

tables = ['Alarms','Areas', 'Cameras', 'Controllers', 'Doors', 'EventFilters', 
         'FloorPlans', 'FloorPlanSymbols', 'Intercoms', 'LineData', 'LinePointsData', 
         'PGMs', 'Roles', 'SecurityLevels', 'Sites', 'TroubleZones'
         ] # This should be the same as the modules import above. To extend this application, write a module named like same as the table you want and add the name here.

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
        engine = create_engine(connection_url)

        # Test connection 
        with engine.connect() as connection:
            sql_query = pd.read_sql(f''' 
                                        SELECT * FROM [SecurityExpert].[dbo].[Controllers];
                                        '''
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
                            'PWD='+ password+';'
                            'TrustServerCertificate=Yes;'
                            )
            connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": cnxn_string})
            engine = create_engine(connection_url)

            # Test connection 
            with engine.connect() as connection:
                sql_query = pd.read_sql(f''' 
                                            SELECT * FROM [SecurityExpert].[dbo].[Controllers];
                                            '''
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
        logging.error(' Unable to create backup directory. Check file and folder creation permissions!')
    else:
        logging.error(' Directory name already exists!')

def ReadTable(cursor, tableName: str):
    tsql = f'SELECT * FROM [SecurityExpert].[dbo].[{tableName}];'   #TODO: add exception for reading CARDS from the FloorPlans DB
    with cursor.execute(tsql):
        #cursor.commit()
        row = cursor.fetchall() # convert to fetchmany(batchSize) because fetchall() stores everything in RAM
        return row
        #i = 0; 
        #while(i < row.__len__()):
        #    print (row[i])
        #    i+=1

def SqlSelectInto(cursor, tableName: str):
    tsql = f'SELECT * INTO [{tableName}_{datetime.utcnow().replace(microsecond=0).isoformat()}] FROM [SecurityExpert].[dbo].[{tableName}];'
    with cursor.execute(tsql):
        cursor.commit()

# Description: Writes a SQL table to a CSV file and puts it in a certain folder, depending on operation.
# Takes: cnxn - pyODBC connection, tableName, operation - 0 is working set, 1 is backup
# Returns: nothing
def WriteTableToFile(cnxn, tableName: str, operation: bool):
    with cnxn.connect() as connection:
        sql_query = pd.read_sql(f''' 
                                    SELECT * FROM [SecurityExpert].[dbo].[{tableName}];
                                    '''
                                    ,connection) # here, the 'conn' is the variable that contains your database connection information from step 2
    df = pd.DataFrame(sql_query)
    if operation: 
        # Take a backup with the dirname above (it is created at start of script!)
        path = Path() / dirname / f'{tableName}.csv'
    else: 
        # Use same method to create working set, avoids code duplication
        path = Path() / 'working_set' / f'{tableName}.csv'
    df.to_csv (path, index = False)


# Description: Fetches a working set dataframe (TODO: don't hardcode, make it more general)
# Takes: tableName - name of the Dataframe(in the form of a CSV, ofc), string
# Returns: nothing / TODO: error msgs or exceptions   -  ALSO: add this to modules and make it not require a param? Also implement protections (even if CheckCSV() is for that exact purpose)
def FetchWSDataFrame(tableName: str):
    path = Path().cwd() / 'working_set' / f'{tableName}.csv'
    return pd.read_csv(path)


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
    sites = Sites()
    controllers = Controllers()
    floorplans = FloorPlans()

    # Run preprocess for all objects, ORDER IS IMPORTANT!
    path = Path() / GetBackupDirsPath()[-1] / 'Sites.csv'
    sites.FetchAndPreprocess(cnxn, path)
    sites.Restore(cnxn)

    # if there are Sites IDs to process | TODO: try to reduce coupling between objects, taken to separate method
    if sites.dictdf.empty:
        logging.debug(' No Sites to restore...')

    path = Path() / GetBackupDirsPath()[-1] / 'Controllers.csv'
    controllers.FetchAndPreprocess(cnxn, path)
    controllers.ProcessIDs(sites.dictdf)
    controllers.Restore(cnxn)

    if controllers.dictdf.empty:
        logging.debug(' No Controllers to restore...')




# Description: Backs up the remote SQL tables and 
# Takes: cnxn - SQL connection info
# Returns: nothing / TODO: maybe error msgs?
def BackupAll(cnxn):
    # Create the backup folder
    CreateBackupDirPath()
    # Take a normal backup
    for table in tables:
        WriteTableToFile(cnxn, table, 1)

# Process working set dir before restoring!
def SetupWorkingSetDir():
    path = Path() / 'working_set'

    # if it exists, remove it, DO NOT PUT OTHER STUFF IN IT, IT WILL BE REMOVED TOO
    if path.is_dir():
        try:
            shutil.rmtree(path)
        except OSError as e:
            logging.error(f' Failed to remove {e.filename} folder! Error msg: {e.strerror} ')
    # then make it again, so it's empty
    path.mkdir()

def GetBackupDirsPath():
    dirs = []
    for d in Path().iterdir():
        if d.is_dir() and fnmatch.fnmatch(d, 'backup_*'):
            dirs.append(d)
    dirs.sort(key = os.path.getmtime)
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


def CompareCSV(cnxn, tableName: str, path: Path) -> pd.DataFrame:
    #prevCwd = os.getcwd()
    #os.chdir(os.path.join(prevCwd, path))   # change working dir to current backup dir TODO: THIS WILL BREAK IF CUSTOM PATH IS SELECTED, FIX getDirs() TO GIVE FULL PATHS!
    #logging.debug(os.getcwd())

    df1 = pd.read_sql(f''' 
                        SELECT * FROM [SecurityExpert].[dbo].[{tableName}];
                        '''
                        ,cnxn)
    csv_path = path / f'{tableName}.csv'
    df2 = pd.read_csv(csv_path)

    logging.debug(df1)
    
    if df1.size > df2.size:
        logging.warning(' The database has more records than the backup. It may be intentional, but you also may not have an up-to-date full backup of your data.')
    #difference = df1.loc[~df1['Name'].isin(df2['Name'])]    # TODO: figure out a way to get reliable info about possibly changed or re-added FloorPlans... CURRENTLY ONLY FILTERS BY NAME AND DOESNT STOP FOR CARD TEMPLATES

    df2['is_equal'] = np.where(df2['Name'].isin(df1['Name']), True, False) # make a new col in df2 that compares the names of objects between the dataframes 

    logging.debug(df2)

    df2 = df2.loc[~df2['is_equal'], :] # copy-less removal of everything with attribute 'True' (we want the differences)

    # TODO: compare df's by the Name, then crawl through the IDs in order 

    
    logging.debug(df2.empty)


    #os.chdir(prevCwd)   # return to parent dir at end
    #logging.debug(os.getcwd())
    return df2
    
## ------------------------     Main      ------------------------
def main():
    logging.Logger.setLevel(logging.getLogger(), level='DEBUG')
    #print(logging.getLogger().getEffectiveLevel())

    print ('Reading data from table')   # define connection (for pandas) and cursor (for pyODBC)
    cnxn = Connect()
    #cursor = cnxn.cursor()

    
    
    #for tb in tables: 
    #    writeTableToFile(cnxn, tb, 1)

    #CompareCSV(cnxn, 'FloorPlans', GetBackupDirsPath()[-1])
    #CheckCSV()

    # this code block finds all child folders starting with 'backup_'
    #dirs = [name for name in os.listdir('.') if os.path.isdir(name)]
    #dirs.sort(key=os.path.getmtime)
    #dirs = [d for d in dirs if d.startswith('backup_')]

    #print(dirs)

    #print(getBackupDirsPath())
    # self-explanatory
    SetupWorkingSetDir()

    # Create the main menu
    menu = ConsoleMenu('Security Expert pyTools', 'Schneider Electric Bulgaria')    

    # Set up the Backup and Restore submenus
   
    backup_menu = ConsoleMenu(title='Backup to files submenu')
    backup_func = FunctionItem(text='Backp F-n', function=BackupAll, menu=backup_menu)
    backup_menu.append_item(backup_func)
    backup_dir_submenuitem = SubmenuItem('Backup', submenu=backup_menu, menu=menu)
    
    restore_menu = ConsoleMenu(title='Restore to DB submenu')
    restore_func = FunctionItem(text='Restore F-n', function=RestoreAll, args=[cnxn], menu=restore_menu)
    restore_menu.append_item(restore_func)
    restore_dir_submenuitem = SubmenuItem('Restore', submenu=restore_menu, menu=menu)

    menu.append_item(backup_dir_submenuitem)
    menu.append_item(restore_dir_submenuitem)

    menu.show()
    menu.join()

    #selection = backup_menu.selected_option
    
    #print(selection+1)

    
   # directory = pathlib.Path().absolute()
    #print(max([os.path.join(directory,d) for d in os.listdir(directory)], key=os.path.getmtime))
    #print(next(os.walk('.'))[1])
    #print(list(filter(os.path.isdir, [os.path.join(directory, f) for f in os.listdir(directory)])))
   # Controllers.buildWorkingSet('./backup_13_12_2022_15-21-24') # dirnames will be handled in a separate method



if __name__ == '__main__':
    main()