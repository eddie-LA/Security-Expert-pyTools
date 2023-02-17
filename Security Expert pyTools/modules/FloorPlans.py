from ast import parse
from pathlib import Path
import pandas as pd
import numpy as np
import pyodbc
import logging
import shutil

class FloorPlans:
    table_name = 'FloorPlans'
    date_fields = ['PostPrintDateTimeData','LastModified','Created']

    def __init__(self):
        self.dictdf = pd.DataFrame() # this DF will keep track of old IDs and the new computed IDs, it will be used as a disctionary when crawling through the objects and fixing mismatched IDs 
        self.tempdf = pd.DataFrame() # this DF will keep track of the changes (after comparing backed up DF to remote DF) that need to be sent to the DB
        #self.ready = False # set this to True when you're sure all IDs are set correctly

    def Backup(self, cnxn, bPath: Path): # this takes the Path defined in the main script
        with cnxn.begin() as conn:
            df = pd.read_sql_query(f'SELECT * FROM [SecurityExpert].[dbo].[{self.table_name}];'
                                           ,con=conn
                                           ,parse_dates=self.date_fields
                                           ) # here, the 'conn' is the variable that contains your database connection information from step 2
        
        # Backup images to the same folder with names = name of FloorPlan
        for image_path, row_name in zip(df['BackgroundImage'], df['Name']):
            if image_path:  # check if path is empty, no need to work with empties
                src_path = Path(image_path)
                dest_path = bPath.parent / f'{row_name}.jpg'
                #print(dest_path)
                #print(Path().absolute())
                try:
                    shutil.copy2(src=src_path, dst=dest_path) # attempt to copy the images and their metadata, ONLY WORKS WHEN SCRIPT IS RUN LOCALLY (same machine as images)
                except FileNotFoundError as e:  # print out an error if images are not found!
                    print(e)

        df.to_csv(bPath, sep=';', index = False) # <--- TODO: UNCOMMENT THIS! 

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
        #difference = df1.loc[~df1['Name'].isin(df2['Name'])]    # TODO: figure out a way to get reliable info about possibly changed or re-added FloorPlans... CURRENTLY ONLY FILTERS BY NAME AND DOESNT STOP FOR CARD TEMPLATES

        df2['is_equal'] = np.where(df2['Name'].isin(df1['Name']), True, False) # make a new col in df2 that compares the names of objects between the dataframes 

        df2 = df2.loc[~df2['is_equal'], :] # copy-less removal of everything with attribute 'True' (we want the differences)

        df2 = df2.drop(columns='is_equal') # remove the now redundant 'is_equal 'column

        self.tempdf = df2 # this is the DF that will be uploaded 

    # Handle Sites, RecordGroup
    def ProcessIDs(self, dictdf_sites: pd.DataFrame):
        # if empty DF, do nothing, we have nothing to restore and it means self.dictdf will be empty too
        if self.tempdf.empty:
            logging.debug(' The buffer dataframe is empty! There are no entries to restore. Exiting method...')
            return -1 # return type is up for... reconsideration

        # ----- Get info for any changes in SiteIDs and apply any differences here | TODO: handle orphaned data?
        if not dictdf_sites.empty:
            self.tempdf['SiteID'] = self.tempdf['SiteID'].replace([dictdf_sites['Old'].values], [dictdf_sites['New'].values])

        # Solve RecordGroups by zeroing all of them, which have a value | TODO: May be better to just set them all to 'no value' (2147483647)
        #self.tempdf['RecordGroup'] = np.where(self.tempdf['RecordGroup'] == 2147483647, 2147483647, 0)
        self.tempdf['RecordGroup'] = 2147483647


    def Restore(self, cnxn, bPath: Path): # maybe name this Preprocess(), rather than Restore()
        # requires: working set dataframe
        # this gets executed ONLY AFTER code in main has executed CompareCSVtoDB() over all tables and has set all offsets EVERYWHERE
        # returns 0 or error code

        # if empty DF, do nothing, we have nothing to restore and it means dictdf is empty too
        if self.tempdf.empty:
            logging.debug(' The buffer dataframe is empty! There are no entries to restore. Exiting method...')
            return -1 # return type is up for... reconsideration

        # -- Code block: Restore images (ONLY FOR ONES EXISTING IN CURRENT FOLDER)
        for image_path, row_name in zip(self.tempdf['BackgroundImage'], self.tempdf['Name']):
            if image_path:                                                  # check if path is empty, no need to work with empties
                path = bPath.parent / f'{row_name}.jpg'                     # make the path var
                image_path = path.__str__                                   # convert to string and set
        # -- End Code block

        # drop the rest, unfortunately it needs to be done row by row, so split the df in a df_list, we may want to keep having the tempdf though...
        df_list = [d for _, d in self.tempdf.groupby('FloorPlanID')] 

        # Modify list in-place to remove NaNs and cols meant to be autofilled by the DB (identity and Rowversion/timestamp). Optimization: merge this with the next loop, may break stuff silently
        for index, df in enumerate(df_list):
            df_list[index] = (df_list[index].drop(columns=['FloorPlanID'])
                                            .dropna(axis='columns')
            )
        # ------------------------------- probably cut method here, move to upper method and return df_list
        with cnxn.connect() as conn:
            for df in df_list:
                #print(df)
                df.to_sql(f'{self.table_name}', con=conn, if_exists='append', index=False)

        # ------------------------------------------------------------ probably cut method here and make a new one from code below - named Postprocess()
        df_list_names = self.tempdf['Name'].values

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

        self.dictdf = pd.DataFrame({'Old': self.tempdf['FloorPlanID'].values, 
                                    'New': df_readback['FloorPlanID'].values
                                    })

        print(self.dictdf)
