import scm.obj as obj
import argparse
import json
import sys
import logging
import time
from config import ConfigurationManager
from scm import PanApiHandler
from scm.process import Processor, SCMObjectManager
from logging.handlers import TimedRotatingFileHandler
from api import PanApiSession
import re
import gjson
import dictdiffer
import pandas
import ssl
import copy
import difflib
import itertools
from typing import List, Tuple, Iterator

## Temporary setup to ignore SSL warning
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Legacy Python that doesn't verify HTTPS certificates by default
    pass
else:
    # Handle target environment that doesn't support HTTPS verification
    ssl._create_default_https_context = _create_unverified_https_context

api_session = ""
scope_param = ""

# https://github.com/PaloAltoNetworks/panos-to-scm


def setup_logging():
    logger = logging.getLogger('')
    logger.setLevel(logging.DEBUG)
    
    handler = TimedRotatingFileHandler('debug-log.txt', utc=True, when="midnight", interval=1, backupCount=1)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)

def setup_scm_object_manager(session, obj_types, sec_obj, nat_obj, scope_param):
    return SCMObjectManager(session, scope_param, obj, obj_types, sec_obj, nat_obj)

def initialize_api_session():
    session = PanApiSession()
    session.authenticate()
    return session

def run_selected_objects(parsed_data, scm_obj_manager, scope_param, device_group_name, run_objects_list):
    selected_obj_types = [obj for obj in config.obj_types if obj.__name__ in run_objects_list]
    
    if not selected_obj_types:
        logger.warning(f"No valid objects found to run for {run_objects_list}")
        return
    
    scm_obj_manager.process_objects(parsed_data, scope_param, device_group_name, max_workers=6, limit=config.limit)


def initialise():
    global api_session
    global scope_param
    scope_type = input("Do you want to use a folder or a snippet? Enter 'folder' or 'snippet': ").strip().lower()
    scope_value = input(f'Enter the {scope_type} name (Use "All" for "Global", "Shared" for "Prisma Access"): ').strip()
    config_type = 'local'
    
    if scope_type == "":
        scope_type = "folder"
    if scope_value == "":
        scope_value = "Shared"

    scope_param = f"&{scope_type}={scope_value}"
    print (f"Scope {scope_type} value: {scope_value}")

    api_session = PanApiHandler(initialize_api_session())

def patch_rule(action, **kwargs):
    global api_session
    global scope_param
    # selected_obj_types = [obj for obj in config.obj_types if obj.__name__ in run_objects_list] if run_objects else config.obj_types
    scm_obj_manager = setup_scm_object_manager(api_session, [], config.sec_obj, config.nat_obj, scope_param)
    # scm_obj_manager.process_rules(config.sec_obj, parsed_data, file_path, limit=config.limit, rule_type='security')
    current_rules_pre = scm_obj_manager.fetch_rules(config.sec_obj, limit='100000', position='pre')
    current_rules_post = scm_obj_manager.fetch_rules(config.sec_obj, limit='100000', position='post')
    # print (json.dumps(current_rules_pre,indent=4))

    if kwargs.get("dryrun",True) == False:
        logger.info("Running in execution run mode")
    else:
        logger.info("Running in dry run mode")
    
    if kwargs['position'] == 'pre':
        current_rules = current_rules_pre
    if kwargs['position'] == 'post':
        current_rules = current_rules_post
    # print (current_rules)
    if action == "add":
        new_rule  = kwargs['rule'] 
        position = kwargs['position']
        logger.info(f"Add new rule : {new_rule}, position: {position}")
        extra_query_param = f"position={kwargs['position']}"
        if kwargs.get("dryrun",True) == False:
            scm_obj_manager.configure.post_entries(scope_param, new_rule, obj.SecurityRule, extra_query_params=extra_query_param)

    if action == "update":
        
        position = kwargs['position']
        rulenames = kwargs.get('rulenames',[])
        filter = kwargs.get('filter',"")
        rule_exclude = kwargs.get('rule_exclude',[])

        if len(rule_exclude) >= 1:
            rule_names = gjson.get(current_rules,"#.name")
            rulenames = list(set(rule_names) - set (rule_exclude))
            logger.info("Excluding rules")
            logger.info (f"Total Rules - {len(rule_names)} - Excluded Rules {len(rule_exclude)} - Affected rules {len(rulenames)}")
       
        for rule in current_rules:
            old_rule = copy.deepcopy(rule)
            if filter != "":

                filter_field = filter.keys()[0]
                # if type(rule[filter_field]) == dict:
                #     if rule[filter_field] == filter[]
            if rule['name'] in rulenames or "all-rules" in rulenames[0]:

                if rulenames[0] == "all-rules-allow" and rule['action'] == "deny":
                    # continue if we want only allow rule but found deny rule
                    logger.info(f"rule {rule['name']} - Change all-rules-allow found deny rule - skipping")
                    continue

                if rulenames[0] == "all-rules-deny" and rule['action'] == "allow":
                    # continue if we want only deny rule but found deny rule
                    logger.info(f"rule {rule['name']} - Change all-rules-deny found allow rule - skipping")
                    continue
                
                
                logger.info(f"Found rule to be updated - name {rule['name']} - id {rule['id']}")
                endpoint = f"/sse/config/v1/security-rules/{rule['id']}?position={position}{scope_param}"
                logger.info(f"Endpoint : {endpoint}")
                
                # delete profile group
                
                logger.info(f"endpoint {endpoint}")
                
                objects = kwargs.get('objects',{})
                # objects_value = kwargs.get('objects_value',[])
                
                rule_update = False

                if len(objects) >=1:
                    for index,object_key in enumerate(objects):
                        object_value = objects[object_key]

                        if rule[object_key] !=  object_value:
                            logger.info(f"Object value not match object:{object_key} current value: {rule[object_key]} new value: {object_value} - Updating")
                            rule[object_key] = object_value
                            rule_update = True
                        else:
                            logger.info(f"Object value already match object:{object_key} current value: {rule[object_key]} new value: {object_value} - skipping")
                            logger.info(f"Object value already match - skipping")

                    if rule_update:
                        logger.info(f"Updating rule - {rule['name']} ")
                        
                        if kwargs.get('fix_logging',False) == True:
                            rule['log_start'] = False
                            rule['log_end'] = True
                            rule['log_setting'] = 'Cortex Data Lake'

                        old_value_text = json.dumps(old_rule, indent=4).splitlines(keepends=True)
                        new_value_text = json.dumps(rule, indent=4).splitlines(keepends=True)
                        # table = tabulate([[old_value_text, new_value_text]], headers=['Old Value', 'New Value'], tablefmt='orgtbl')
                        table = Sdiffer().dump_sdiff(old_value_text, new_value_text)
                        logger.info(f"Comparison: \n{table}")

                        ## remark next line if you want to testing
                        if kwargs.get("dryrun",True) == False and rule_update:
                            scm_obj_manager.api_handler.put(endpoint,rule)
                        else:
                            logger.info(f'Skipping update, dryrun: {kwargs.get("dryrun",True)}')
                

                

    if action == "delete":
        rulenames = kwargs['rulenames']
        position = kwargs['position']
        for rule in current_rules:
            if rule['name'] in rulenames or rulenames=="all":
                logger.info(f"Found rule to be deleted - name {rule['name']} - id {rule['id']}")
                endpoint = f"/sse/config/v1/security-rules/{rule['id']}?position={position}{scope_param}"
                logger.info(f"Endpoint : {endpoint}")
                if kwargs.get("dryrun",True) == False:
                    scm_obj_manager.api_handler.delete(endpoint)

    if action == "user_format":
        position = kwargs['position']
        rulenames = kwargs['rulenames']
        new_user_format = []
        for rule in current_rules_pre:
            if rule['name'] in rulenames:
                logger.info(f"Found rule to be updated - name {rule['name']} - id {rule['id']}")
                endpoint = f"/sse/config/v1/security-rules/{rule['id']}?position={position}{scope_param}"
                logger.info(f"Endpoint : {endpoint}")
                # if kwargs['object'] in rule.keys():
                for user in rule['source_user']:
                    if "dc" in user:
                        # cn=group 1,cn=users,dc=testlab,dc=corp
                        result = re.search("^cn=(.+?),", user)
                        if result:
                            user_in_rule = result.group(1)
                        logger.info(f"user: {user} captured user: {user_in_rule} - format: ldap")
                    elif "\\" in user:
                        result = re.search("^(.+)\\\(.+)", user)
                        if result:
                            (realm, user_in_rule) = result.groups()
                        if "." in realm:
                            logger.info(f"user: {user} captured user: {user_in_rule} captured realm: {realm} - format: Azure-AD-Netbios")
                        else:
                            logger.info(f"user: {user} captured user: {user_in_rule} captured realm: {realm} - format: Netbios")
                    elif "@" in user:
                        # cn=group 1,cn=users,dc=testlab,dc=corp
                        result = re.search("^(.+)@(.+)", user)
                        if result:
                            (user_in_rule,domain) = result.groups
                        logger.info(f"user: {user} captured user: {user_in_rule} - domain: {domain} format: upn")
                    else:
                        logger.info(f"user: {user} format not identified")

                # rule[kwargs['object']] = kwargs['object_value']
                logger.info(f"new value: {json.dumps(rule,indent=4)}")
                logger.info(f"endpoint {endpoint}")
                if kwargs.get("dryrun",True) == False:
                    scm_obj_manager.api_handler.put(endpoint,rule)

 
def read_file(filename):
    with open(filename, "r") as f:
        return f.read().splitlines()

def do_replicate(input_file,**kwargs):
    ### replicate json config
    global api_session
    global scope_param

    if kwargs.get("dryrun",True) == False:
        logger.info("Running in execution run mode")
    else:
        logger.info("Running in dry run mode")

    # selected_obj_types = [obj for obj in config.obj_types if obj.__name__ in run_objects_list] if run_objects else config.obj_types
    scm_obj_manager = setup_scm_object_manager(api_session, [], config.sec_obj, config.nat_obj, scope_param)
    # scm_obj_manager.process_rules(config.sec_obj, parsed_data, file_path, limit=config.limit, rule_type='security')
    
    # input file = json file of the security rule
    
    with open(input_file) as f:
        input = json.load(f)
    
    current_rules_pre = scm_obj_manager.fetch_rules(config.sec_obj, limit='100000', position='pre')
    current_rules_post = scm_obj_manager.fetch_rules(config.sec_obj, limit='100000', position='post')
    if kwargs['position'] == 'pre':
        current_rules = current_rules_pre
    if kwargs['position'] == 'post':
        current_rules = current_rules_post
    position = kwargs['position']
    

    for rule in current_rules:
        for input_rule in input:
            if rule['name'] == input_rule['name']:
                logger.info(f"Found rule to be updated - name {rule['name']} - id {rule['id']}")
                endpoint = f"/sse/config/v1/security-rules/{rule['id']}?position={position}{scope_param}"
                logger.info(f"Endpoint : {endpoint}")
                # logger.info(f"new value: {json.dumps(rule,indent=4)}")
                # delete uuid
                rule_id = rule['id']
                del(rule['id'])
                del(input_rule['id'])
                diff1 = dictdiffer.diff(rule,input_rule)
                diff2 = list(diff1)
                if diff2 == []:
                    logger.info("Rule is the same")
                else:
                    # print (list(diff1))
                    logger.info(f"diff: {json.dumps(diff2,indent=4)}")
                    rule1 = input_rule
                    rule1['id'] = rule_id
                    logger.info(f"new value: {json.dumps(rule1,indent=4)}")
                    if kwargs.get("dryrun",True) == False:
                        scm_obj_manager.api_handler.put(endpoint,rule1)
                        
def backup(format='json', folder='./'):
    """ 
    Backup SCM config
    """
    import datetime

    global api_session
    global scope_param
    # selected_obj_types = [obj for obj in config.obj_types if obj.__name__ in run_objects_list] if run_objects else config.obj_types
    logger.info(f"Backup Config - output {format}, folder={folder}")
    scm_obj_manager = setup_scm_object_manager(api_session, [], config.sec_obj, config.nat_obj, scope_param)
    tsg = api_session.session.get_tsg()
    cur_time = datetime.datetime.now()
    time_stamp = f"{cur_time.year}-{cur_time.month}-{cur_time.day}_{cur_time.hour}-{cur_time.minute}-{cur_time.second}"
    pre_rules = scm_obj_manager.fetch_rules(config.sec_obj, limit='100000', position='pre')
    post_rules = scm_obj_manager.fetch_rules(config.sec_obj, limit='100000', position='post')
    result = scm_obj_manager.get_current_objects(config.obj_types)
    result1 = {}
    for entry in result:
        obj_name = entry._endpoint.split("/")[-1][:-1]
        result1[obj_name] = result[entry]

    if format.lower() == 'json':
        with open(f"{folder}/{tsg}-scm-pre-rules-{time_stamp}.json","w") as f:
            f.write(json.dumps(pre_rules,indent=4))

        with open(f"{folder}/{tsg}-scm-post-rules-{time_stamp}.json","w") as f:
            f.write(json.dumps(post_rules,indent=4))

        with open(f"{folder}/{tsg}-scm-objects-{time_stamp}.json","w") as f:
            f.write(json.dumps(result1,indent=4))
    
    if format.lower() == 'xlsx':
        
        pre_rules_df = pandas.DataFrame(pre_rules)
        pre_rules_df.to_excel(f"{folder}/{tsg}-scm-pre-rules-{time_stamp}.xlsx")
        post_rules_df = pandas.DataFrame(post_rules)
        post_rules_df.to_excel(f"{folder}/{tsg}-scm-post-rules-{time_stamp}.xlsx")
        with pandas.ExcelWriter(f"{folder}/{tsg}-scm-objects-{time_stamp}.xlsx", engine='xlsxwriter') as writer:
            for res in result1:
                df = pandas.DataFrame(result1[res])
                df.to_excel(writer, sheet_name=res[:31])

class Sdiffer:
    def __init__(self, max_width:int = 80):
        # Two columns with a gutter
        self._col_width = (max_width - 3) // 2
        assert self._col_width > 0
        
    def _fit(self, s: str) -> str:
        s = s.rstrip()[:self._col_width]
        return  f"{s: <{self._col_width}}"

    def sdiff(self, a: List[str], b: List[str]) -> Iterator[str]:
        diff_lines = difflib.Differ().compare(a, b)
        diff_table: List[Tuple[str, List[str], List[str]]] = []
        diff_table.append((" ",[">>>> Old Value <<<<"],[">>>> New Value <<<<"]))
        for diff_type, line_group in itertools.groupby(diff_lines, key=lambda ln: ln[:1]):
            lines = [ln[2:] for ln in line_group]
            if diff_type == " ":
                diff_table.append((" ", lines, lines))
            else:
                if not diff_table or diff_table[-1][0] != "|":
                    diff_table.append(("\33[31m"+"<>"+"\033[0m", [], []))
                if diff_type == "-":
                    # Lines only in `a`
                    diff_table[-1][1].extend(lines)
                elif diff_type == "+":
                    # Lines only in `b`
                    diff_table[-1][2].extend(lines)

        for diff_type, cell_a, cell_b in diff_table:
            for left, right in itertools.zip_longest(cell_a, cell_b, fillvalue=""):
                yield f"{self._fit(left)} {diff_type} {self._fit(right)}"
    
    def dump_sdiff(self, a: List[str], b: List[str]) -> Iterator[str]:
        return "\n".join(self.sdiff(a, b))

def process_input(objects_str, objects_value_str):

    # objects_str='["service","to","description"]'
    # objects_value_str = '[["service-http"],["untrust"],"hello123"]'

    objects = eval(objects_str)
    objects_value  = eval(objects_value_str)
    a = {}
    if len(objects) != len(objects_value):
        logger.error ("Length of Object and object value are not same")

    for index,object in enumerate(objects):
        a[objects[index]] = objects_value[index]

    return a

def patch(dryrun=True, objects_str='', objects_value_str='', rules='', rule_file='', position='post'):
    """
    Patch SCM Rules
    """

    rules_to_update = []
    if len(rule_file) > 1:
        rules_to_update = read_file(rule_file)

    if len(rules) > 1:
        rules_to_update = eval(rules)
    
    if len(rules_to_update) < 1:
        logger.error("Rules or rule file name must be provided")
        sys.exit(1)

    logger.info ("Running Patch")
    source_hip = ['OCBC-Default-HIP-Profile']

    objects = process_input(objects_str, objects_value_str)
    
    patch_rule("update",objects=objects, position=position, rulenames=rules, fix_logging = True, dryrun=dryrun)
    # patch_rule("update",objects="source_hip",object_value=source_hip, position=position, rulenames=rules, fix_logging = True, dryrun=dryrun)

    logger.info ("Finish Patch")
    
    # replicate("scm-post-rules-2024-12-18_17-50-24.json", position="post")
    # replicate("test-china.json", position="post")

def replicate(dryrun=True, input_file='input.json', position='post'):
    """
    Replicate SCM json rule
    This only replicate rules that are already exists in the system
    To run replicate, you need:
    1. Make a backup config of the source tenant
    2. Update config.yml to point to the target tenant
    3. Execute
    """
    logger.info("Running replicate")
    logger.info(f"Input file: {input_file}, Position: {position}")
    do_replicate(input_file, position=position, dryrun=dryrun)
    logger.info ("Finish replicate")

if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger(__name__)
    begin_time = time.time()

    parser = argparse.ArgumentParser(description="SCM Utility and Patcher")
    parser.add_argument('-c','--config',action='store',default='~/.panapi/config.yml')
    
    subparsers = parser.add_subparsers(dest='command', required=True, help='command')

    backup_parsers = subparsers.add_parser('backup', help="Backup SCM Config")
    backup_parsers.add_argument('-f', dest='format', choices=['json','xlsx'], help="Backup Output format", default='json')
    backup_parsers.add_argument('-o', dest='folder', action='store', help="Backup folder", default='./')

    patcher_parser = subparsers.add_parser('patch', help="patch SCM Rule Config")
    patcher_parser.add_argument('-nd',dest='nodryrun',help="Dry Run", action='store_true', default=False)
    patcher_parser.add_argument('--objects',dest='objects',help="Field objects to be replaced", action='store', default='')
    patcher_parser.add_argument('--values',dest='values',help="Objects values", action='store', default='')
    patcher_parser.add_argument('--rules',dest='rules',help="Rules to be update, or use one of these - all-rules, all-rules-allow, all-rules-deny", action='store', default='')
    patcher_parser.add_argument('--rule_file',dest='rule_file',help="Rule file name", action='store', default='')
    patcher_parser.add_argument('-p', '--position', choices=['pre','post'], default='post')

    replicate_parser = subparsers.add_parser('replicate', help="replicate SCM Config")
    replicate_parser.add_argument('-f', '--file', action='store', default='scm-rule.json')
    replicate_parser.add_argument('-p', '--position', choices=['pre','post'], default='post')
    replicate_parser.add_argument('-nd',dest='nodryrun',help="No Dry Run", action='store_true', default=False)

    args = parser.parse_args() 

    initialise()

    config_manager = ConfigurationManager(args.config)
    config = config_manager.app_config

    if args.command == 'backup':
        backup(folder=args.folder,format=args.format)

    if args.command == 'patch':
        patch(dryrun=not args.nodryrun, objects_str=args.objects, objects_value_str=args.values, rules=args.rules, rule_file=args.rule_file, position=args.position)

    if args.command == 'replicate':
        replicate(dryrun=not args.nodryrun, input_file=args.file, position=args.position)
    
    
    
    


