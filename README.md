# PostFlashPreTestCheck
## Description
Query for the stub version used in the software and check for CAN Tx messages by the target based on DBC files.

## Requirements
Aside from the libraries listed in the requirements.txt file, I used the following:
*  [Python 3.7](https://www.python.org/downloads/release/python-370/)
*  Vector VN1630A

### What's in `requirements.txt`?
*  python-can 3.0.0

## Usage
### Before anything else..
*  The addresses of StubVersion_Main and StubVersion_Sub are still static (defined in the source code)
*  DBC files should be in the following folder structure relative to the script folder:
```
   ./DBC
      |- <variant 1>
         |- FILE1_var1.dbc
         |- FILE2_var1.dbc
         |- FILE3_var1.dbc
         |- FILE4_var1.dbc
      |- <variant 2>
         |- FILE1_var2.dbc
         |- FILE2_var2.dbc
         |- FILE3_var2.dbc
         |- FILE4_var2.dbc
      :
      |- <variant n>
         |- FILE1_var3.dbc
         |- FILE2_var3.dbc
         |- FILE3_var3.dbc
         |- FILE4_var3.dbc
```
*  DBC files are CAN channel-specific. Thus, the script should be updated with the proper channel-DBC configuration

### Command line syntax
```
py PostFlashPreTestCheck.py
```

## What's next?
*  Automatically update the addresses of StubVersion_Main and StubVersion_Sub
*  Make the pairing of the CAN channel and DBC file optional to the user