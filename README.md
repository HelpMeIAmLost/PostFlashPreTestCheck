# PostFlashPreTestCheck
## Description
Query for the stub version used in the software and check for CAN Tx messages by the target based on DBC files.

## Requirements
Aside from the libraries listed in the requirements.txt file, I used the following:
*  [Python 3.7](https://www.python.org/downloads/release/python-370/)
*  Vector VN1630A

### What's in `requirements.txt`?
*  python-can 3.0.0
*  numpy 1.15.3

## Usage
### Before anything else..
*  The addresses of StubVersion_Main and StubVersion_Sub are still static (defined in the source code)
*  DBC files should be in the following folder structure relative to the script folder (DBC file names could be different:
```
   ./DBC
      |- <variant 1>
         |- FILE1_<var 1>.dbc
         |- FILE2_<var 1>.dbc
         |- FILE3_<var 1>.dbc
         |- FILE4_<var 1>.dbc
      |- <variant 2>
         |- FILE1_<var 2>.dbc
         |- FILE2_<var 2>.dbc
         |- FILE3_<var 2>.dbc
         |- FILE4_<var 2>.dbc
      :
      |- <variant n>
         |- FILE1_<var n>.dbc
         |- FILE2_<var n>.dbc
         |- FILE3_<var n>.dbc
         |- FILE4_<var n>.dbc
```
*  DBC files are CAN channel-specific. Thus, the script should be updated with the proper channel-DBC file configuration

### Command line syntax
```
py PostFlashPreTestCheck.py
```

## What's next?
*  The location of MAP and DBC files are, by default, set to `Build/` and `DBC/` folders, respectively. Commandline arguments will be added in case these locations need to be changed.