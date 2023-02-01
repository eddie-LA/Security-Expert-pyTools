from ast import parse
from pathlib import Path
import pandas as pd
import numpy as np
import pyodbc
import logging

class Sites:
    table_name = 'Sites'
    date_fields = ['DefaultUserStartDate','DefaultUserExpiryDate','OneTimeStartTime','StartingAt','StartingAt2','EndingAt','StartDate','EndDate','ExportLastRunTime','ExportNextRunTime','WirelessCredentialsLastSyncTime','LastModified','Created']

    def __init__(self):
        self.dictdf = pd.DataFrame() # this DF will keep track of old IDs and the new computed IDs, it will be used as a disctionary when crawling through the objects and fixing mismatched IDs 
        self.tempdf = pd.DataFrame() # this DF will keep track of the changes (after comparing backed up DF to remote DF) that need to be sent to the DB
        #self.ready = False # set this to True when you're sure all IDs are set correctly

    def Backup(self, cnxn, bPath: Path): # this takes the Path defined in the main script
        df = pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[{self.table_name}];'
                                       ,con=cnxn
                                       ,parse_dates=self.date_fields
                                       ) # here, the 'conn' is the variable that contains your database connection information from step 2
        
        # Take a backup with the table_name above (it is created at start of script!)
        #print(Path().cwd())
        #print(bPath)
        df.to_csv(bPath, sep=';', index = False)

    def FetchAndPreprocess(self, cnxn, bPath: Path): # this takes the Path defined in the main script | TODO: add check for separator contained in table content somewhere?
        df1 = pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[{self.table_name}];'
                                ,con=cnxn
                                ,parse_dates=self.date_fields
                                )

        df2 = pd.read_csv(bPath
                          ,sep=';'
                          ,parse_dates=self.date_fields
                          ,infer_datetime_format=True
                          )

        if df1.size > df2.size:
            logging.warning(' The database has more records than the backup. It may be intentional, but you also may not have an up-to-date full backup of your data.')
        #difference = df1.loc[~df1['Name'].isin(df2['Name'])]    # TODO: figure out a way to get reliable info about possibly changed or re-added FloorPlans... CURRENTLY ONLY FILTERS BY NAME AND DOESNT STOP FOR CARD TEMPLATES

        df2['is_equal'] = np.where(df2['Name'].isin(df1['Name']), True, False) # make a new col in df2 that compares the names of objects between the dataframes 

        df2 = df2.loc[~df2['is_equal'], :] # copy-less removal of everything with attribute 'True' (we want the differences)

        df2 = df2.drop(columns='is_equal') # remove the now redundant 'is_equal 'column

        self.tempdf = df2 # this is the DF that will be uploaded 
        

    def ProcessIDs(self):
        logging.debug(' There are no foreign IDs to handle in Sites. This method is a placeholder. It only exists in order to conform to the interface.')
        pass

    def Restore(self, cnxn): # maybe name this Preprocess(), rather than Restore()
        # requires: working set dataframe
        # this gets executed ONLY AFTER code in main has executed CompareCSVtoDB() over all tables and has set all offsets EVERYWHERE
        # returns 0 or error code

        # if empty DF, do nothing, we have nothing to restore and it means dictdf is empty too
        if self.tempdf.empty:
            logging.debug(' The buffer dataframe is empty! There are no entries to restore. Exiting method...')
            return -1 # return type is up for... reconsideration

        # drop the rest, unfortunately it needs to be done row by row, so split the df in a df_list, we may want to keep having the tempdf though...
        df_list = [d for _, d in self.tempdf.groupby('SiteID')] 

        # Modify list in-place to remove NaNs and cols meant to be autofilled by the DB (identity and Rowversion/timestamp). Optimization: merge this with the next loop, may break stuff silently
        for index, df in enumerate(df_list):
            df_list[index] = (df_list[index].drop(columns=['SiteID'])
                                            .dropna(axis='columns')
            )
        # ------------------------------- probably cut method here, move to upper method and return df_list
        with cnxn.connect() as connection:
            for df in df_list:
                #print(df)
                df.to_sql(f'{self.table_name}', connection, if_exists='append', index=False)

        # ------------------------------------------------------------ probably cut method here and make a new one from code below - named Postprocess()
        df_list_names = self.tempdf['Name'].values

        # now we need to read what IDs the DB has given to the restored objects
        df_readback = pd.DataFrame()
        with cnxn.connect() as connection:
            for name in df_list_names:  # this loop may be able to be optimized and removed by using Name IN (?) and a stringified list, but for now that doesn't seem to work
                df_readback = pd.concat([df_readback,
                                    pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[{self.table_name}] WHERE Name=(?);'
                                                                        ,con=cnxn
                                                                        ,parse_dates=self.date_fields
                                                                        ,params=[name])
                                            ]
                                            ,ignore_index=True)
        #print('printing readback df')
        #print(df_readback)

        self.dictdf = pd.DataFrame({'Old': self.tempdf['SiteID'].values, 
                                    'New': df_readback['SiteID'].values
                                    })

        print(self.dictdf)