from ast import parse
from pathlib import Path
import pandas as pd
import numpy as np
import pyodbc
import logging

class Areas:
    table_name = 'Areas'
    date_fields=['LastModified','Created']

    def __init__(self):
        self.dictdf = pd.DataFrame() # this DF will keep track of old IDs and the new computed IDs, it will be used as a disctionary when crawling through the objects and fixing mismatched IDs 
        self.tempdf = pd.DataFrame() # this DF will keep track of the changes (after comparing backed up DF to remote DF) that need to be sent to the DB

    def Backup(self, cnxn, bPath: Path): # this takes the Path defined in the main script
        with cnxn.begin() as conn:
            df = pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[{self.table_name}];'
                                           ,con=conn
                                           ,parse_dates=self.date_fields
                                           ) # here, the 'conn' is the variable that contains your database connection information from step 2
        
            # Take a backup with the table_name above (it is created at start of script!)
            #print(Path().cwd())
            #print(bPath)
        df.to_csv(bPath, sep=';', index = False)

    def FetchAndPreprocess(self, cnxn, bPath: Path): # this takes the Path defined in the main script | TODO: add check for separator contained in table content somewhere?
        with cnxn.begin() as conn:
            df1 = pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[{self.table_name}];'
                                    ,con=conn
                                    ,parse_dates=self.date_fields
                                    )

        df2 = pd.read_csv(bPath
                          ,sep=';'
                          ,parse_dates=self.date_fields
                          ,infer_datetime_format=True
                          )

        if df1.size > df2.size:
            logging.warning(' The database has more records than the backup. It may be intentional, but you also may not have an up-to-date full backup of your data.')

        df2['is_equal'] = np.where(df2['Name'].isin(df1['Name']), True, False) # make a new col in df2 that compares the names of objects between the dataframes 

        df2 = df2.loc[~df2['is_equal'], :] # copy-less removal of everything with attribute 'True' (we want the differences)

        # TODO: compare df's by the Name, then crawl through the IDs in order 

        df2 = df2.drop(columns='is_equal') # remove the now redundant 'is_equal 'column

        self.tempdf = df2 # this is the DF that will be uploaded 

    # Description:
    # Takes:
    # Returns: 
    # Handle Controllers, ChildArea (?), PGMs - BellPGMOutput ExitDelayPGMOutput EntryDelayPGMOutput, LoiterResetArea (may need AreaGroup and PGMGroup too..., else set to INT MAX but that isn't a good solution)
    # -- left to handle: AreaGroups, PGMGroups and self-referencing values
    def ProcessIDs(self, dictdf_ctrlrs: pd.DataFrame, dictdf_pgms: pd.DataFrame):
        # if empty DF, do nothing, we have nothing to restore and it means self.dictdf will be empty too
        if self.tempdf.empty:
            logging.debug(' The buffer dataframe is empty! There are no entries to restore. Exiting method...')
            return -1 # return type is up for... reconsideration

        # ----- Get info for any changes in SiteIDs, FloorPlan IDs, Camera IDs and apply any differences here | TODO: handle orphaned data?
        if not dictdf_ctrlrs.empty:
            self.tempdf['ControllerID'] = self.tempdf['ControllerID'].replace([dictdf_ctrlrs['Old'].values], [dictdf_ctrlrs['New'].values])

        if not dictdf_pgms.empty:
            self.tempdf['BellPGMOutput'] = self.tempdf['BellPGMOutput'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['ExitDelayPGMOutput'] = self.tempdf['ExitDelayPGMOutput'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['EntryDelayPGMOutput'] = self.tempdf['EntryDelayPGMOutput'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['DisarmedPGMOutput'] = self.tempdf['DisarmedPGMOutput'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['ArmedPGMOutput'] = self.tempdf['ArmedPGMOutput'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['BypassedZonesPGMOutput'] = self.tempdf['BypassedZonesPGMOutput'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['TamperAlarmPGMOutput'] = self.tempdf['TamperAlarmPGMOutput'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['AlarmMemoryPGMOutput'] = self.tempdf['AlarmMemoryPGMOutput'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['UserCountReachedPGMOutput'] = self.tempdf['UserCountReachedPGMOutput'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['AreaDeferArmingStartedPGMOutput'] = self.tempdf['AreaDeferArmingStartedPGMOutput'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['ReadyPGM'] = self.tempdf['ReadyPGM'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])

        # reset ChildArea and LoiterResetArea to 2147483647, currently not handling same-table-referencing entries
        self.tempdf['ChildArea'] = 2147483647
        self.tempdf['LoiterResetArea'] = 2147483647


    def Restore(self, cnxn): # maybe name this Preprocess(), rather than Restore()
        # requires: working set dataframe
        # this gets executed ONLY AFTER code in main has executed CompareCSVtoDB() over all tables and has set all offsets EVERYWHERE
        # returns 0 or error code

        # read backed up DF and working set DF

        # if empty DF, do nothing, we have nothing to restore and it means dictdf is empty too
        if self.tempdf.empty:
            logging.debug(' The buffer dataframe is empty! There are no entries to restore. Exiting method...')
            return -1 # return type is up for... reconsideration

        # drop the rest, unfortunately it needs to be done row by row, so split the df in a df_list, we may want to keep having the tempdf though...
        df_list = [d for _, d in self.tempdf.groupby('AreaID')] 

        # Modify list in-place to remove NaNs and cols meant to be autofilled by the DB (identity and Rowversion/timestamp). Optimization: merge this with the next loop, may break stuff silently
        for index, df in enumerate(df_list):
            df_list[index] = (df_list[index].drop(columns=['AreaID'])
                                            .dropna(axis='columns')
            )
        # ------------------------------- probably cut method here, move to upper method and return df_list
        with cnxn.connect() as conn:
            for df in df_list:
                #print(df)
                df.to_sql(f'{self.table_name}',con=conn, if_exists='append', index=False)

        # ------------------------------------------------------------ probably cut method here and make a new one from code below - named Postprocess(), above - Restore()
        df_list_names = self.tempdf['Name'].values
        #df_list_names = ','.join(f"'{name}'" for name in self.tempdf['Name'].values)   # an attempt at collecting the names in a string to pass as 1 SQL Select below
        #print('Printing names...')
        #print(df_list_names)

        # now we need to read what IDs the DB has given to the restored objects
        df_readback = pd.DataFrame()
        with cnxn.connect() as conn:
            for name in df_list_names:  # this loop may be able to be optimized and removed by using Name IN (?) and a stringified list, but for now that doesn't seem to work
                df_readback = pd.concat([df_readback,
                                    pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[{self.table_name}] WHERE Name=(?);'
                                                      ,con=conn
                                                      ,parse_dates=self.date_fields
                                                      ,params=[name]
                                                      )
                                    ]
                                        ,ignore_index=True)
        #print('printing readback df')
        #print(df_readback)

        self.dictdf = pd.DataFrame({'Old': self.tempdf['AreaID'].values, 
                                    'New': df_readback['AreaID'].values
                                    })

        print(self.dictdf)
        #print(self.dictdf['Old'].values)
        #print(self.dictdf['New'].values)