# Security-Expert-pyTools

Welcome! This repo is meant to be a collection of tools for SE Security Expert. 
Its main (and only) current purpose is to facilitate backup and restore operations on floor plans, as the software itself notably has this functionality missing.
The application can backup and restore data locally, as well as remotely. Locally, it will also backup and restore all images used in the floor plans. 
Remotely, it *cannot* backup and restore images and will output warnings, this is intended. 

| Requirements |
| ----------- |
| MS ODBC Driver for SQL server 18 [(here)](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server?view=sql-server-ver16) | 
| Python 3.9  | 
| pandas 1.5 |
| pyodbc 4.0 |
| sqlalchemy 1.4 *(2.0 not supported by pandas yet)* |
| nuitka 1.4 *(optional, if you want to make an .exe)* |

## Functionality 
| Backup | Backs up all floor plan data and images to human-readable format (CSV and JPG/PNG) to separate subfolder, which incldes time and date in its name |
| -------- | ---- | 

Two modes of restoration exist:
| Simple | Restore picked floor plan data and images, objects are restored as well but with minimal or default settings. All custom data is *not* restored |
| ----------- | ---- | 
| Full *(WIP)* | Restore the data from the picked floor plans fully, including relations between objects and object data |

There is going to be a **log file** created in the folder, where the tool is located and launched in.

## To make an .exe:
    python -m nuitka --standalone Security_Expert_pyTools.py

The resulting .exe or folder with .exe will be located in the 'Security_Expert_pyTools.dist' subfolder on the current console path.

<br/><br/>

## Usage
When you use the tool, whether like a python app or like a C app through nuitka, you will be presented with a prompt to enter an IP, username and password.

If you want to connect in Local mode (using Windows Credentials), you can leave the username and password fields blank.

If you want to connect in SQL Authentication mode, create a user account/password combo for your SecurityExpert DB.

&nbsp;&nbsp; **WARNING:** Before using the tool for restoring, make sure that SecurityExpert and all its services are stopped! 

&nbsp;&nbsp; **WARNING 2:** It's **highly recommended** to backup your database in any case, because things can *always* go wrong! Follow the several backups methodology to protect your data! Info on how to backup your DB [here](https://learn.microsoft.com/en-us/sql/relational-databases/backup-restore/create-a-full-database-backup-sql-server?view=sql-server-ver16).


### Create local account for SecurityExpert DB

#### Using Microsoft SQL Server Management Studio
1. Open SSMS and login
2. Click > Security > Logins
3. Right click on Logins and choose 'New Login'
4. Enter the username and select 'SQL Server Authentication', then enter your password and preferred options
5. You may set the Default database to SecurityExpert, if you like.
6. Choose 'User Mapping' on the left hand side of the window and enable the SecurityExpert and SecurityExpertEvents checkboxes.
7. Click OK.

#### Using T-SQL:
    -- Creates the login MyUser with password 'passwd1!'.  
    CREATE LOGIN MyUser   
        WITH PASSWORD = 'passwd1!';  
    GO  

    -- Creates a database user for the login created above.  
    CREATE USER MyUser FOR LOGIN MyUser;  
    GO  
