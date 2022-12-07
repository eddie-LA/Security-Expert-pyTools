import pyodbc
from datetime import datetime

# Connection information:
# You are likely to have 
server = '192.168.202.128'
database = 'SECURITYEXPERT'

## ---------------------- DB Connection ----------------------
# Attempt local connection...
connected = False;
try:
    cnxn = pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};'
                            'SERVER='+server+';'
                            'DATABASE='+database+';'
                            'Trusted_Connection=yes;'
                            'TrustServerCertificate=Yes;'
                            )
    print(f'Successfully connected to {database} using Windows credentials')
    connected = True
except:
    print("Local DB connection using Windows Credentials attempt failed. Trying to connect using a username/passwd...");


# If it fails, you may connect to the DB via username/passwd. Usually the username is 'sa' and the passwd is the one you entered in the installation.
# It may not have access to the SECURITYEXPERT databases though.
## You can also create a new user in SSMS and use that. (recommended)
username = 'external'
password = '1qaz2wsx'

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
        print(f"Successfully connected to {database} using username/passwd")
    except:
        print("Connection to DB using username/passwd failed.")
cursor = cnxn.cursor()

## --------------------- Method declarations ---------------------
def readTable(tableName):
    #tsql = f'SELECT * INTO [{tableName}_{datetime.utcnow().replace(microsecond=0).isoformat()}] FROM [SecurityExpert].[dbo].[{tableName}];'
    tsql = f'SELECT * FROM [SecurityExpert].[dbo].[{tableName}];'
    with cursor.execute(tsql):
        #cursor.commit()
        row = cursor.fetchall() # convert to fetchmany(batchSize) because fetchall() stores everything in RAM
        print(row)
        #i = 0; 
        #while(i < row.__len__()):
        #    print (row[i])
        #    i+=1

## ------------------------     Main      ------------------------
print ('Reading data from table')
readTable("floorplans")
