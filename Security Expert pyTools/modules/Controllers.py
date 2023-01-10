import pandas as pd
import os

def backup(cnxn, dirname, tableName='Controllers'):
    sql_query = pd.read_sql_query(f''' 
                                    SELECT * FROM [SecurityExpert].[dbo].[{tableName}];
                                    '''
                                    ,cnxn) # here, the 'conn' is the variable that contains your database connection information from step 2
    df = pd.DataFrame(sql_query)
    path = os.path.join(os.getcwd(), dirname)
    df.to_csv (os.path.join(path, f'{tableName}.csv'), index = False)

def buildWorkingSet(dirname):
    # check backup folder
    # get working set CSV
    
    # get backup CSV
    print(os.getcwd())
    os.chdir(dirname)
    print(os.getcwd())
    # put CSVs from both working set and backup folder in dataframes
    # compare names
    # get controllers from backup that don't exist in working set
    # offset IDs of objects by max ID of working set controllers
    # return dataframe and ID offset amount
    # ... handle exceptions

    pass

def restore(wsDF):
    # requires: working set dataframe
    # this gets executed ONLY AFTER code in main has executed buildWorkingSet() over all tables and has set all offsets EVERYWHERE
    # returns 0 or error code
    pass