import os
import fnmatch
import pyodbc
import pandas as pd
from datetime import datetime
import logging

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

tableNames = ['Alarms','Areas', 'Cameras', 'Controllers', 'Doors', 'EventFilters', 
                'FloorPlans', 'FloorPlanSymbols', 'Intercoms', 'LineData', 'LinePointsData', 
                'PGMs', 'Roles', 'SecurityLevels', 'Sites', 'TroubleZones'
                ]

## ---------------------- DB Connection ----------------------
# Attempt local connection...
def connect():
    connected = False;
    try:
        cnxn = pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};'
                                'SERVER='+server+';'
                                'DATABASE='+database+';'
                                'Trusted_Connection=yes;'
                                'TrustServerCertificate=Yes;'
                                )
        logging.info(f'Successfully connected to {database} using Windows credentials')
        connected = True
    except:
        logging.warning("Local DB connection using Windows Credentials attempt failed. Trying to connect using a username/passwd...");


# In order to keep encryption, but without the need for a trusted root certificate (those cost money and are not necessary here), trust the server certificate
# You may use ODBC Driver 18 and 17 as well - https://learn.microsoft.com/en-us/sql/connect/odbc/windows/release-notes-odbc-sql-server-windows?view=sql-server-ver16
    if connected == False:
        try:
            cnxn = pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};'
                                  'SERVER='+server+';'
                                  'DATABASE='+database+';'
                                  'UID='+username+';'
                                  'PWD='+ password+';'
                                  'TrustServerCertificate=Yes;'
                                  )
            logging.info(f"Successfully connected to {database} using username/passwd")
        except:
            logging.warning("Connection to DB using username/passwd failed.")
    return cnxn

## --------------------- Method declarations ---------------------
def createBackupDir():
    if not os.path.exists(dirname):
        try: 
            os.makedirs(dirname)
        except:
            logging.error('Unable to create backup directory. Check file and folder creation permissions!')
    else:
        logging.error('Directory name already exists!')

def readTable(cursor, tableName):
    tsql = f'SELECT * FROM [SecurityExpert].[dbo].[{tableName}];'   #TODO: add exception for reading CARDS from the FloorPlans DB
    with cursor.execute(tsql):
        #cursor.commit()
        row = cursor.fetchall() # convert to fetchmany(batchSize) because fetchall() stores everything in RAM
        return row
        #i = 0; 
        #while(i < row.__len__()):
        #    print (row[i])
        #    i+=1

def sqlSelectInto(cursor, tableName):
    tsql = f'SELECT * INTO [{tableName}_{datetime.utcnow().replace(microsecond=0).isoformat()}] FROM [SecurityExpert].[dbo].[{tableName}];'
    with cursor.execute(tsql):
        cursor.commit()

def writeTableToFile(cnxn, tableName):
    sql_query = pd.read_sql_query(f''' 
                                    SELECT * FROM [SecurityExpert].[dbo].[{tableName}];
                                    '''
                                    ,cnxn) # here, the 'conn' is the variable that contains your database connection information from step 2
    df = pd.DataFrame(sql_query)
    path = os.path.join(os.getcwd(), dirname)
    df.to_csv (os.path.join(path, f'{tableName}.csv'), index = False)

def sqlSelect(cursor, tableName):
    # unify selects ? 
    pass

# TODO: check pandas.read_sql_query backwards, whether it works okay, compare to original table
def writeFileToDb(cursor, fileName):

    pass

def compareRemoteToCurrent(cnxn, tableName):
    sql_query = pd.read_sql_query(f''' 
                                   SELECT * FROM [SecurityExpert].[dbo].[{tableName}];
                                   '''
                                   ,cnxn) # the 'cnxn' is the variable that contains the DB connection information

    pass

def getBackupDirs():
    dirs = []
    for dir in os.listdir():
        if os.path.isdir(dir) and fnmatch.fnmatch(dir, 'backup_*'):
            dirs.append(dir)
    return dirs

# By default path is latest backup dir, BUT a custom path may be specified!
# - List of dirs from getDirs() should already be sorted with the latest dir at the end!


def pickBackup(cnxn, tableName, path):
    prevCwd = os.getcwd()
    os.chdir(os.path.join(prevCwd, path))   # change working dir to current backup dir TODO: THIS WILL BREAK IF CUSTOM PATH IS SELECTED, FIX getDirs() TO GIVE FULL PATHS!
    #logging.debug(os.getcwd())

    df1 = pd.read_sql_query(f''' 
                             SELECT * FROM [SecurityExpert].[dbo].[{tableName}];
                             '''
                             ,cnxn)
    df2 = pd.read_csv(f'{tableName}.csv')

    difference = df1.loc[~df1["Name"].isin(df2['Name'])]    # TODO: figure out a way to get reliable info about possibly changed or readded FloorPlans... CURRENTLY ONLY FILTERS BY NAME AND DOESNT STOP FOR CARD TEMPLATES

    # TODO: compare df's by the

    print(df1)
    print(df2)
    print(difference)
    
    os.chdir(prevCwd)   # return to parent dir at end
    #logging.debug(os.getcwd())
    
    

## ------------------------     Main      ------------------------
def main():
    logging.Logger.setLevel(logging.getLogger(), level='DEBUG')
    #print(logging.getLogger().getEffectiveLevel())

    print ('Reading data from table')   # define connection (for pandas) and cursor (for pyODBC)
    cnxn = connect()
    cursor = cnxn.cursor()

    
    #createBackupDir()
    #for tb in tableNames: 
    #    writeTableToFile(cnxn, tb)

    pickBackup(cnxn, 'FloorPlans', getBackupDirs()[-1])

    
    #sqlSelectInto("FloorPlanSymbols")

if __name__ == "__main__":
    main()