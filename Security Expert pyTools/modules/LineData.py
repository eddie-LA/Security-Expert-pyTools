from ast import parse
from pathlib import Path
import pandas as pd
import numpy as np
import pyodbc
import logging

class LineData:
    table_name = 'LineData'
    date_fields = []

    def __init__(self):
        self.dictdf = pd.DataFrame() # this DF will keep track of old IDs and the new computed IDs, it will be used as a disctionary when crawling through the objects and fixing mismatched IDs 
        self.tempdf = pd.DataFrame() # this DF will keep track of the changes (after comparing backed up DF to remote DF) that need to be sent to the DB

    def Backup(self, cnxn, bPath: Path): # this takes the Path defined in the main script
        with cnxn.begin() as conn:
            df = pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[{self.table_name}];'
                                           ,con=conn
                                           ) # here, the 'conn' is the variable that contains your database connection information from step 2
        
        # Backup images to the same folder with names = name of FloorPlan

        df.to_csv(bPath, sep=';', index = False) # <--- TODO: UNCOMMENT THIS! 
        #AND HANDLE ImagePath from the DB! (appears unused but who knows...)
        # Also handle Camera and JumpToFloorPlan (maybe check if plan with that ID exists on the DB using Name col in backup
        # -- if YES (likely because not existing FPs get restored in a prev step): get new ID of that FP and put it here before restore
        # -- if NO: set to 2147483647 and output Warning
        # DeviceControllerID (controllers) and DeviceAddressID (with DeviceTypeID filtering) handle in ProcessIDs
        # Camera if not 2147483647 set OLD to NEW

    def FetchAndPreprocess(self, bPath: Path, dictdf_fp: pd.DataFrame): # this method is different due to the intrinsic link of LineData to FloorPlans
    #def FetchAndPreprocess(self, cnxn, bPath: Path, dictdf_fp: pd.DataFrame): 
        #with cnxn.begin() as conn:
        #    df1 = pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[{self.table_name}];'
        #                            ,con=conn
        #                            )
        # --> Currently, FPs with an existing name will not be restored, so only check CSV and consequently dict_df of FPs for objects to restore.
        # If you want to restore a FP to its older version, just delete it and the tool will restore it as it was.
        df2 = pd.read_csv(bPath
                          ,sep=';'
                          )
        # Check only IDs of FPs that exist in the backup 
        # Get 'Old' col of dictdf of FPs and filter IDs to restore by that
        # -- Code is very similar to the other modules, but requires dict_df of FloorPlans
        df2['to_remove'] = np.where(df2['FloorPlanID'].isin(dictdf_fp['Old']), False, True) # make a new col in df2 that checks if a given FP ID is going to be restored, True and False are flipped, because we want to keep the entries that fit the criteria

        df2 = df2.loc[~df2['to_remove'], :] # copy-less removal of everything with attribute 'True' (we want the similarities)

        df2 = df2.drop(columns='to_remove') # remove the now redundant 'to_remove 'column

        self.tempdf = df2 # this is the DF that will be restored 

        
    def ProcessIDs(self, dictdf_fp: pd.DataFrame, dictdf_cam: pd.DataFrame, dictdf_doors: pd.DataFrame):
        # if empty DF, do nothing, we have nothing to restore and it means self.dictdf will be empty too
        if self.tempdf.empty:
            logging.debug(' The buffer dataframe is empty! There are no entries to restore. Exiting method...')
            return -1 # return type is up for... reconsideration

        # ----- Get info for any changes in FloorPlanID and apply any differences here | TODO: handle orphaned data?
        if not dictdf_fp.empty:
            self.tempdf['FloorPlanID'] = self.tempdf['FloorPlanID'].replace([dictdf_fp['Old'].values], [dictdf_fp['New'].values])

        # Solve RecordGroups by zeroing all of them, which have a value | TODO: May be better to just set them all to 'no value' (2147483647)
        #self.tempdf['RecordGroup'] = np.where(self.tempdf['RecordGroup'] == 2147483647, 2147483647, 0)
        #self.tempdf['RecordGroup'] = 2147483647


    def Restore(self, cnxn): # maybe name this Preprocess(), rather than Restore()
        # requires: working set dataframe
        # this gets executed ONLY AFTER code in main has executed CompareCSVtoDB() over all tables and has set all offsets EVERYWHERE
        # returns 0 or error code

        # if empty DF, do nothing, we have nothing to restore and it means dictdf is empty too
        if self.tempdf.empty:
            logging.debug(' The buffer dataframe is empty! There are no entries to restore. Exiting method...')
            return -1 # return type is up for... reconsideration

        # drop the rest, unfortunately it needs to be done row by row, so split the df in a df_list, we may want to keep having the tempdf though...
        df_list = [d for _, d in self.tempdf.groupby('ID')] 

        # Modify list in-place to remove NaNs and cols meant to be autofilled by the DB (identity and Rowversion/timestamp). Optimization: merge this with the next loop, may break stuff silently
        for index, df in enumerate(df_list):
            df_list[index] = (df_list[index].drop(columns=['ID'])
                                            .dropna(axis='columns')
            )
        # ------------------------------- probably cut method here, move to upper method and return df_list
        with cnxn.connect() as conn:
            for df in df_list:
                #print(df)
                df.to_sql(f'{self.table_name}', con=conn, if_exists='append', index=False)

        # ------------------------------------------------------------ probably cut method here and make a new one from code below - named Postprocess()
        df_list_names = list(dict.fromkeys(self.tempdf['FloorPlanID'].values)) # remove duplicates and preserve order by temporarily converting to dict

        # now we need to read what IDs the DB has given to the restored objects
        df_readback = pd.DataFrame()
        with cnxn.connect() as conn:
            for name in df_list_names:  # this loop may be able to be optimized and removed by using Name IN (?) and a stringified list, but for now that doesn't seem to work
                df_readback = pd.concat([df_readback,
                                    pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[{self.table_name}] WHERE FloorPlanID=(?);'
                                                      ,con=conn
                                                      ,params=[name]
                                                      )
                                    ]
                                    ,ignore_index=True)
        #print('printing readback df')
        #print(df_readback)

        self.dictdf = pd.DataFrame({'Old': self.tempdf['ID'].values, 
                                    'New': df_readback['ID'].values
                                    })

        print(self.dictdf)
