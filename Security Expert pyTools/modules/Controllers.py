from ast import parse
from pathlib import Path
import pandas as pd
import numpy as np
import pyodbc
import logging

class Controllers:
    table_name = 'Controllers'
    date_fields=['TestReport','AutomaticOfflineTime','LastDownloaded','LastModified','Created']

    def __init__(self):
        self.dictdf = pd.DataFrame() # this DF will keep track of old IDs and the new computed IDs, it will be used as a disctionary when crawling through the objects and fixing mismatched IDs 
        self.tempdf = pd.DataFrame() # this DF will keep track of the changes (after comparing backed up DF to remote DF) that need to be sent to the DB
        #self.remotedf = pd.DataFrame() # this DF keeps the remote DB's table in memory, maybe reuse/delete somehow after extracting all the necessary data? -- After saving the ID info, this becomes redundant, so make it an instance var, discardable, for better memory management
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

        #logging.debug(df1)
        #print(df1)
        #print("---new line----")
        #print(df2)

        if df1.size > df2.size:
            logging.warning(' The database has more records than the backup. It may be intentional, but you also may not have an up-to-date full backup of your data.')
        #difference = df1.loc[~df1['Name'].isin(df2['Name'])]    # TODO: figure out a way to get reliable info about possibly changed or re-added FloorPlans... CURRENTLY ONLY FILTERS BY NAME AND DOESNT STOP FOR CARD TEMPLATES

        df2['is_equal'] = np.where(df2['Name'].isin(df1['Name']), True, False) # make a new col in df2 that compares the names of objects between the dataframes 

        #logging.debug(df2)

        df2 = df2.loc[~df2['is_equal'], :] # copy-less removal of everything with attribute 'True' (we want the differences)

        # TODO: compare df's by the Name, then crawl through the IDs in order 
            
        #logging.debug(df2)

        df2 = df2.drop(columns='is_equal') # remove the now redundant 'is_equal 'column

        #logging.debug(df2)

        #self.offset = df1['ControllerID'].max() # set ControllerID offset, this is needed *outside*, so the other objects can update their IDs accordingly

        self.tempdf = df2 # this is the DF that will be uploaded 
        #logging.debug("-------")
        #logging.debug(self.tempdf['ControllerID'])
        #logging.debug("-------")
        # need to set the whole Series of IDs to: ID = offset + X (for X = whichever number object it is) -> ID = pd.Series(range(X)) + offset, maybe use a DF to keep old and new IDs? Use 'values' to drop indices
        #self.dictdf = pd.DataFrame({'Old': self.tempdf['ControllerID'].values, 
        #                            'New': pd.Series(range(self.offset + 1, self.tempdf['ControllerID'].size + self.offset + 1))
        #                            }) # create a DF to hold old IDs of restorables in one col, and create another col to keep newly computed IDs, starting from offset+1 to amount of items we need to save + offset+1 (i.e. start after the max ID of the current table, grow +1 for every item)
        #logging.debug(self.dictdf) # dictdf is THE KEY to managing all the IDs!

        # Disregard internal rowversion/timestamp col
        #df1.drop(columns='Rowversion', inplace=True)
        #self.tempdf.drop(columns='Rowversion', inplace=True)

        ## Disregard ControlledID IDENTITY col, as it's set to not allow inserts
        #df1.drop(columns='ControllerID', inplace=True)
        #self.tempdf.drop(columns='ControllerID', inplace=True)

        #self.tempdf['ControllerID'] = self.dictdf['New'] # set the new IDs, ONLY DO THIS FOR IDs ON YOUR OWN MODULE DEPENDENT ONLY ON ITS RESPECTIVE TABLE (i.e. Controllers to Controllers, FloorPlans to FloorPlans ONLY), the IDs foreign to the objects get matched in main using dictdf
        
        #return df2  # may turn out not necessary ... we need the data to stick, so save in the object instead!

    # Description:
    # Takes:
    # Returns: 
    def ProcessIDs(self, dictdf_sites: pd.DataFrame):
        # if empty DF, do nothing, we have nothing to restore and it means self.dictdf will be empty too
        if self.tempdf.empty:
            logging.debug(' The buffer dataframe is empty! There are no entries to restore. Exiting method...')
            return -1 # return type is up for... reconsideration

        # ----- Get info for any changes in SiteIDs and apply any differences here | TODO: handle orphaned data?
        if not dictdf_sites.empty:
            self.tempdf['SiteID'] = self.tempdf['SiteID'].replace([dictdf_sites['Old'].values], [dictdf_sites['New'].values])


    def Restore(self, cnxn): # maybe name this Preprocess(), rather than Restore()
        # requires: working set dataframe
        # this gets executed ONLY AFTER code in main has executed CompareCSVtoDB() over all tables and has set all offsets EVERYWHERE
        # returns 0 or error code

        # read backed up DF and working set DF
        # find differences - possible duplication with parent's CompareCSV()?

        # if empty DF, do nothing, we have nothing to restore and it means dictdf is empty too
        if self.tempdf.empty:
            logging.debug(' The buffer dataframe is empty! There are no entries to restore. Exiting method...')
            return -1 # return type is up for... reconsideration

        # drop NaN values, as tables usually have a no NULL policy, and where NULL is allowed, it's the default, so we don't care about it anyway
        # a NULL value here means a default or nonexisting value in the DB, dropping cols here allows the DB to fill the missing cols with default values
        # create a copy, as we will need self.tempdf to compare in the future
        #df1 = self.tempdf.copy()
        #print('------ Printing dtypes -------')
        #print(df1.dtypes)
        #df1 = (df1.drop(columns=['ControllerID','Rowversion'])
        #               .dropna(axis='columns')
        #               )

        # drop the rest, unfortunately it needs to be done row by row, so split the df in a df_list, we may want to keep having the tempdf though...
        df_list = [d for _, d in self.tempdf.groupby('ControllerID')] 

        # Modify list in-place to remove NaNs and cols meant to be autofilled by the DB (identity and Rowversion/timestamp). Optimization: merge this with the next loop, may break stuff silently
        for index, df in enumerate(df_list):
            df_list[index] = (df_list[index].drop(columns=['ControllerID','Rowversion'])
                                            .dropna(axis='columns')
            )
        # ------------------------------- probably cut method here, move to upper method and return df_list
        with cnxn.connect() as connection:
            for df in df_list:
                #print(df)
                df.to_sql(f'{self.table_name}', connection, if_exists='append', index=False)

        # ------------------------------------------------------------ probably cut method here and make a new one from code below - named Postprocess(), above - Restore()
        df_list_names = self.tempdf['Name'].values
        #df_list_names = ','.join(f"'{name}'" for name in self.tempdf['Name'].values)   # an attempt at collecting the names in a string to pass as 1 SQL Select below
        #print('Printing names...')
        #print(df_list_names)

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

        self.dictdf = pd.DataFrame({'Old': self.tempdf['ControllerID'].values, 
                                    'New': df_readback['ControllerID'].values
                                    })

        print(self.dictdf)
        #print(self.dictdf['Old'].values)
        #print(self.dictdf['New'].values)








        