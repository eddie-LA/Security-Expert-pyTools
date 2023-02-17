from ast import parse
from pathlib import Path
import pandas as pd
import numpy as np
import pyodbc
import logging

class Doors:
    table_name = 'Doors'
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
    # Handle Areas, SlaveDoors (oh boy...), Cameras - Entry Exit Autopopup, FloorPlans, PGMs, Intercoms, (RecordGroups)  | TODO: search for changed IDs in remote DB if not found in backup?
    def ProcessIDs(self, dictdf_controllers: pd.DataFrame, dictdf_areas: pd.DataFrame, 
                   dictdf_cams: pd.DataFrame, dictdf_fps: pd.DataFrame, dictdf_pgms: pd.DataFrame, 
                   dictdf_intercoms: pd.DataFrame, dictdf_doortypes: pd.DataFrame, 
                   dictdf_scheds: pd.DataFrame, dictdf_doorgroups: pd.DataFrame,
                   dictdf_pgmgroups: pd.DataFrame, dictdf_zones: pd.DataFrame,
                   dictdf_elevators: pd.DataFrame
                   ):
        # if empty DF, do nothing, we have nothing to restore and it means self.dictdf will be empty too
        if self.tempdf.empty:
            logging.debug(' The buffer dataframe is empty! There are no entries to restore. Exiting method...')
            return -1 # return type is up for... reconsideration

        # ----- Get info for any changes in SiteIDs and apply any differences here | TODO: handle orphaned data?
        if not dictdf_controllers.empty:
            self.tempdf['ControllerID'] = self.tempdf['ControllerID'].replace([dictdf_controllers['Old'].values], [dictdf_controllers['New'].values])
            self.tempdf['HostControllerRef'] = self.tempdf['HostControllerRef'].replace([dictdf_controllers['Old'].values], [dictdf_controllers['New'].values])
            #self.tempdf['HLIControllerID'] = self.tempdf['HLIControllerID'].replace([dictdf_controllers['Old'].values], [dictdf_controllers['New'].values])

        if not dictdf_areas.empty:
            self.tempdf['AreaInsideDoor'] = self.tempdf['AreaInsideDoor'].replace([dictdf_areas['Old'].values], [dictdf_areas['New'].values])
            self.tempdf['AreaOutsideDoor'] = self.tempdf['AreaOutsideDoor'].replace([dictdf_areas['Old'].values], [dictdf_areas['New'].values])

        if not dictdf_cams.empty:
            self.tempdf['CameraEntry'] = self.tempdf['CameraEntry'].replace([dictdf_cams['Old'].values], [dictdf_cams['New'].values])
            self.tempdf['CameraExit'] = self.tempdf['CameraExit'].replace([dictdf_cams['Old'].values], [dictdf_cams['New'].values])
            self.tempdf['AutoPopupCamera'] = self.tempdf['AutoPopupCamera'].replace([dictdf_cams['Old'].values], [dictdf_cams['New'].values])

        if not dictdf_fps.empty:
            self.tempdf['FloorPlan'] = self.tempdf['FloorPlan'].replace([dictdf_fps['Old'].values], [dictdf_fps['New'].values])

        if not dictdf_pgms.empty:
            self.tempdf['PreAlarmPGMOutput]'] = self.tempdf['PreAlarmPGMOutput'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['LeftOpenAlarmPGMOutput'] = self.tempdf['LeftOpenAlarmPGMOutput]'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['ForcedOpenPGMOutput'] = self.tempdf['ForcedOpenPGMOutput'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['LockPGM'] = self.tempdf['LockPGM'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['Lock2PGM'] = self.tempdf['Lock2PGM'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['Lock3PGM'] = self.tempdf['Lock3PGM'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['Lock4PGM'] = self.tempdf['Lock4PGM'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['Lock5PGM'] = self.tempdf['Lock5PGM'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['Lock6PGM'] = self.tempdf['Lock6PGM'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['Function1PGM'] = self.tempdf['Function1PGM'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['Function2PGM'] = self.tempdf['Function2PGM'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])
            self.tempdf['Function3PGM'] = self.tempdf['Function3PGM'].replace([dictdf_pgms['Old'].values], [dictdf_pgms['New'].values])

        if not dictdf_intercoms.empty:
            self.tempdf['IntercomEntry'] = self.tempdf['IntercomEntry'].replace([dictdf_intercoms['Old'].values], [dictdf_intercoms['New'].values])
            self.tempdf['IntercomExit'] = self.tempdf['IntercomExit'].replace([dictdf_intercoms['Old'].values], [dictdf_intercoms['New'].values])

        if not dictdf_doortypes.empty:
            pass

        if not dictdf_scheds.empty:
            pass

        if not dictdf_doorgroups.empty:
            pass

        if not dictdf_pgmgroups.empty:
            pass

        if not dictdf_zones.empty:
            pass

        if not dictdf_elevators.empty:
            pass

        #self.tempdf['RecordGroup'] = 2147483647 # don't handle record groups, the line has to be drawn somewhere | better solution is to just drop the column before inserting, handled in Restore()


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
        df_list = [d for _, d in self.tempdf.groupby('DoorID')] 

        # Modify list in-place to remove NaNs and cols meant to be autofilled by the DB (identity and Rowversion/timestamp).
        for index, df in enumerate(df_list):
            df_list[index] = (df_list[index].drop(columns=['DoorID', 'EnableElevatorHLIDoor', 'ElevatorHLIControllerID','ElevatorHLIDOPFloorGroup', 'IsElevatorHLIDOP', 'ElevatorHLIDOPFloor', 'IsElevatorHLICOP', 'ElevatorHLICOPElevatorGroup', 'HLIControllerType', 'HLIGroupNumber', 'HLIControllerID', 'RecordGroup'])
                                            .dropna(axis='columns')
            )
        # ------------------------------- probably cut method here, move to upper method and return df_list
        with cnxn.connect() as conn:
            for df in df_list:
                #print(df)
                df.to_sql(f'{self.table_name}', con=conn, if_exists='append', index=False)

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

        self.dictdf = pd.DataFrame({'Old': self.tempdf['DoorID'].values, 
                                    'New': df_readback['DoorID'].values
                                    })

        print(self.dictdf)
        #print(self.dictdf['Old'].values)
        #print(self.dictdf['New'].values)
