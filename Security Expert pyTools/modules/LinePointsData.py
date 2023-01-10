import pandas as pd
import os

def backup(cnxn, dirname, tableName='LinePointsData'):
    sql_query = pd.read_sql_query(f''' 
                                    SELECT * FROM [SecurityExpert].[dbo].[{tableName}];
                                    '''
                                    ,cnxn) # here, the 'conn' is the variable that contains your database connection information from step 2
    df = pd.DataFrame(sql_query)
    path = os.path.join(os.getcwd(), dirname)
    df.to_csv (os.path.join(path, f'{tableName}.csv'), index = False)

def restore():
    pass