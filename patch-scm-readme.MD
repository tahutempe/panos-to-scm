
## Overview

The primary use case of this tool is to help with bulk data manipulation of SCM rules. This tool is built on top of panos-scm tool that was deprecated.

```
usage: patch-scm.py [-h] [-c CONFIG] {backup,patch,replicate} ...

SCM Utility and Patcher

positional arguments:
  {backup,patch,replicate}
                        command
    backup              Backup SCM Config
    patch               patch SCM Rule Config
    replicate           replicate SCM Config

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
```

## Backup

This backup command can be used to take a dump of SCM configuration. It can generate output in two formats: JSON, XLSX. There will be 3 output files generated, pre-rule, post-rule and objects

```
usage: patch-scm.py backup [-h] [-f {json,xlsx}] [-o FOLDER]

options:
  -h, --help      show this help message and exit
  -f {json,xlsx}  Backup Output format
  -o FOLDER       Backup folder
```
### Examples

Save config backup in XLSX config

`python patch-scm.py backup -o demo -f xlsx`


## Patch

This patch command can be used to make bulk SCM rule modification such updating HIP profile, etc.
We need to supply the objects, their new values and rule names where the modification will be applied to.

By default the tool will run in dry-run mode, it will take the current and updated values. Once you've confirmed changes, you can run the script again with -nd option to apply the changes.

Rule_file can be used if you want to specify the rules that you want to change in a file rather than specifying it as command line option 
You can also use: ["all-rules"], ["all-rules-allow"], ["all-rules-deny"] for rules parameter.

```
usage: patch-scm.py patch [-h] [-nd] [--objects OBJECTS] [--values VALUES] [--rules RULES] [--rule_file RULE_FILE] [-p {pre,post}]

options:
  -h, --help            show this help message and exit
  -nd                   No Dry Run
  --objects OBJECTS     Field objects to be replaced
  --values VALUES       Objects values
  --rules RULES         Rules to be update
  --rule_file RULE_FILE
                        Rule file name
  -p {pre,post}, --position {pre,post}
```

### Examples

1. Update rule description and service object for policy-1 and policy-2 on pre-rules in dry-run mode

```
python patch-scm.py patch --object "['description','service']" --values "['hello234',['service-https','service-http']]" --rules "['policy-1','policy-2']" -p pre 
```

2. Update rule description and service object for policy-1 and policy-2 on pre-rules without dry run mode

```
python patch-scm.py patch --object "['description','service']" --values "['hello234',['service-https','service-http']]" --rules "['policy-1','policy-2']" -p pre -nd
```


## Sample Output

```
python patch-scm.py patch --object "['description','service']" --values "['hello111',['service-https','service-http']]" --rules "['policy-1','policy-2']" -p pre -nd                                                                                                                                                                   
Do you want to use a folder or a snippet? Enter 'folder' or 'snippet':
Enter the  name (Use "All" for "Global", "Shared" for "Prisma Access"): 12Nov
Scope folder value: 12Nov
2025-02-06 14:59:11,508 - INFO - Token will expire at 2025-02-06 04:14:10.508191
2025-02-06 14:59:11,508 - INFO - Token will expire at 2025-02-06 04:14:10.508757
2025-02-06 14:59:11,511 - INFO - Running Patch
2025-02-06 14:59:11,512 - INFO - Fetching items: https://api.sase.paloaltonetworks.com/sse/config/v1/security-rules?folder=12Nov&limit=5000&offset=0&position=pre
2025-02-06 14:59:13,977 - INFO - Fetching items: https://api.sase.paloaltonetworks.com/sse/config/v1/security-rules?folder=12Nov&limit=5000&offset=0&position=post
2025-02-06 14:59:14,331 - INFO - Running in execution run mode
2025-02-06 14:59:14,331 - INFO - Found rule to be updated - name policy-1 - id 0ddff483-522e-4672-84a4-016529eea50c
2025-02-06 14:59:14,331 - INFO - Endpoint : /sse/config/v1/security-rules/0ddff483-522e-4672-84a4-016529eea50c?position=pre&folder=12Nov
2025-02-06 14:59:14,331 - INFO - endpoint /sse/config/v1/security-rules/0ddff483-522e-4672-84a4-016529eea50c?position=pre&folder=12Nov
2025-02-06 14:59:14,332 - INFO - Object value not match object:description current value: hello234 new value: hello111 - Updating
2025-02-06 14:59:14,332 - INFO - Object value already match object:service current value: ['service-https', 'service-http'] new value: ['service-https', 'service-http'] - skipping
2025-02-06 14:59:14,332 - INFO - Object value already match - skipping
2025-02-06 14:59:14,332 - INFO - Updating rule - policy-1
2025-02-06 14:59:14,335 - INFO - Comparison:
| Old Value                                         | New Value                                         |
|---------------------------------------------------+---------------------------------------------------|
| {                                                 | {                                                 |
|     "id": "0ddff483-522e-4672-84a4-016529eea50c", |     "id": "0ddff483-522e-4672-84a4-016529eea50c", |
|     "name": "policy-1",                           |     "name": "policy-1",                           |
|     "folder": "12Nov",                            |     "folder": "12Nov",                            |
|     "description": "hello234",                    |     "description": "hello111",                    |
|     "from": [                                     |     "from": [                                     |
|         "trust"                                   |         "trust"                                   |
|     ],                                            |     ],                                            |
|     "source": [                                   |     "source": [                                   |
|         "any"                                     |         "any"                                     |
|     ],                                            |     ],                                            |
|     "negate_source": false,                       |     "negate_source": false,                       |
|     "source_user": [                              |     "source_user": [                              |
|         "any"                                     |         "any"                                     |
|     ],                                            |     ],                                            |
|     "source_hip": [                               |     "source_hip": [                               |
|         "any"                                     |         "any"                                     |
|     ],                                            |     ],                                            |
|     "to": [                                       |     "to": [                                       |
|         "untrust"                                 |         "untrust"                                 |
|     ],                                            |     ],                                            |
|     "destination": [                              |     "destination": [                              |
|         "any"                                     |         "any"                                     |
|     ],                                            |     ],                                            |
|     "negate_destination": false,                  |     "negate_destination": false,                  |
|     "destination_hip": [                          |     "destination_hip": [                          |
|         "any"                                     |         "any"                                     |
|     ],                                            |     ],                                            |
|     "application": [                              |     "application": [                              |
|         "any"                                     |         "any"                                     |
|     ],                                            |     ],                                            |
|     "service": [                                  |     "service": [                                  |
|         "service-https",                          |         "service-https",                          |
|         "service-http"                            |         "service-http"                            |
|     ],                                            |     ],                                            |
|     "category": [                                 |     "category": [                                 |
|         "Bypass_Dst"                              |         "Bypass_Dst"                              |
|     ],                                            |     ],                                            |
|     "disabled": false,                            |     "disabled": false,                            |
|     "log_setting": "Cortex Data Lake",            |     "log_setting": "Cortex Data Lake",            |
|     "action": "allow",                            |     "action": "allow",                            |
|     "profile_setting": {                          |     "profile_setting": {                          |
|         "group": [                                |         "group": [                                |
|             "Category-Profile"                    |             "Category-Profile"                    |
|         ]                                         |         ]                                         |
|     },                                            |     },                                            |
|     "log_start": false,                           |     "log_start": false,                           |
|     "log_end": true                               |     "log_end": true                               |
| }                                                 | }                                                 |
2025-02-06 14:59:15,711 - INFO - Found rule to be updated - name policy-2 - id fc4e6a68-dcde-4db5-88bb-c5b1f2bf411d
2025-02-06 14:59:15,711 - INFO - Endpoint : /sse/config/v1/security-rules/fc4e6a68-dcde-4db5-88bb-c5b1f2bf411d?position=pre&folder=12Nov
2025-02-06 14:59:15,711 - INFO - endpoint /sse/config/v1/security-rules/fc4e6a68-dcde-4db5-88bb-c5b1f2bf411d?position=pre&folder=12Nov
2025-02-06 14:59:15,711 - INFO - Object value not match object:description current value: hello234 new value: hello111 - Updating
2025-02-06 14:59:15,711 - INFO - Object value already match object:service current value: ['service-https', 'service-http'] new value: ['service-https', 'service-http'] - skipping
2025-02-06 14:59:15,711 - INFO - Object value already match - skipping
2025-02-06 14:59:15,711 - INFO - Updating rule - policy-2
2025-02-06 14:59:15,714 - INFO - Comparison:
| Old Value                                         | New Value                                         |
|---------------------------------------------------+---------------------------------------------------|
| {                                                 | {                                                 |
|     "id": "fc4e6a68-dcde-4db5-88bb-c5b1f2bf411d", |     "id": "fc4e6a68-dcde-4db5-88bb-c5b1f2bf411d", |
|     "name": "policy-2",                           |     "name": "policy-2",                           |
|     "folder": "12Nov",                            |     "folder": "12Nov",                            |
|     "description": "hello234",                    |     "description": "hello111",                    |
|     "from": [                                     |     "from": [                                     |
|         "trust"                                   |         "trust"                                   |
|     ],                                            |     ],                                            |
|     "source": [                                   |     "source": [                                   |
|         "any"                                     |         "any"                                     |
|     ],                                            |     ],                                            |
|     "negate_source": false,                       |     "negate_source": false,                       |
|     "source_user": [                              |     "source_user": [                              |
|         "ABC\\Regional"                           |         "ABC\\Regional"                           |
|     ],                                            |     ],                                            |
|     "source_hip": [                               |     "source_hip": [                               |
|         "any"                                     |         "any"                                     |
|     ],                                            |     ],                                            |
|     "to": [                                       |     "to": [                                       |
|         "untrust"                                 |         "untrust"                                 |
|     ],                                            |     ],                                            |
|     "destination": [                              |     "destination": [                              |
|         "any"                                     |         "any"                                     |
|     ],                                            |     ],                                            |
|     "negate_destination": false,                  |     "negate_destination": false,                  |
|     "destination_hip": [                          |     "destination_hip": [                          |
|         "any"                                     |         "any"                                     |
|     ],                                            |     ],                                            |
|     "application": [                              |     "application": [                              |
|         "any"                                     |         "any"                                     |
|     ],                                            |     ],                                            |
|     "service": [                                  |     "service": [                                  |
|         "service-https",                          |         "service-https",                          |
|         "service-http"                            |         "service-http"                            |
|     ],                                            |     ],                                            |
|     "category": [                                 |     "category": [                                 |
|         "URLs"                                    |         "URLs"                                    |
|     ],                                            |     ],                                            |
|     "disabled": false,                            |     "disabled": false,                            |
|     "log_setting": "Cortex Data Lake",            |     "log_setting": "Cortex Data Lake",            |
|     "action": "allow",                            |     "action": "allow",                            |
|     "profile_setting": {                          |     "profile_setting": {                          |
|         "group": [                                |         "group": [                                |
|             "Category-Profile"                    |             "Category-Profile"                    |
|         ]                                         |         ]                                         |
|     },                                            |     },                                            |
|     "log_start": false,                           |     "log_start": false,                           |
|     "log_end": true                               |     "log_end": true                               |
| }                                                 | }                                                 |
2025-02-06 14:59:16,722 - INFO - Finish Patch