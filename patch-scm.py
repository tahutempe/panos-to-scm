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

# sample command to run:
# python patch-scm.py 2>&1 | tee cn-removehip1.txt

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
                if rule[kwargs['object']] !=  kwargs['object_value']:
                    logger.info(f"Object value not match object:{kwargs['object']} current value: {rule[kwargs['object']]} new value: {kwargs['object_value']} - Updating")
                    logger.info(f"Updating rule - {rule['name']} ")
                    if kwargs.get("object",'') != '':
                        rule[kwargs['object']] = kwargs['object_value']
                    if kwargs.get('fix_logging',False) == True:
                        rule['log_start'] = False
                        rule['log_end'] = True
                        rule['log_setting'] = 'Cortex Data Lake'
                    logger.info(f"new value: {json.dumps(rule,indent=4)}")

                    ## remark next line if you want to testing
                    if kwargs.get("dryrun",True) == False:
                        scm_obj_manager.api_handler.put(endpoint,rule)
                else:
                    logger.info(f"Object value already match object:{kwargs['object']} current value: {rule[kwargs['object']]} new value: {kwargs['object_value']} - skipping")
                    logger.info(f"Object value already match - skipping")
                

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

def replicate(input_file,**kwargs):
    ### replicate json config
    global api_session
    global scope_param
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
                    # scm_obj_manager.api_handler.put(endpoint,rule1)

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
    

def patch(dryrun=True):
    """
    Patch SCM Config
    Examples:

    ## Predefined rule names
    # ['all-rules-allow'] => all allow rules
    # ['all-rules'] => all rules
    # ['all-rules-deny'] => all deny rules
    
    # Example 1 - Update source_hip field to "any" for all rules. 
    # source_hip = ['any']
    # patch_rule("update",object="source_hip",object_value=source_hip,position="post", rulenames=['all-rules'], fix_logging = True)
    
    # Example 2 - Update set rule policy-158 to disable.
    # disabled = True
    # patch_rule("update",object="disabled",object_value=disabled,position="post", rulenames=['policy-158'], fix_logging = True)
     
    # Example 3 - Update all enabled rules to disable 
    # disabled = True
    # enabled_rules = read_file("remove-hip.txt")
    # patch_rule("update",object="disabled",object_value=disabled,position="post", rule_exclude=enabled_rules, fix_logging = True)
    
    # Example 4 - Update application to web-browsing and ssl for all rules  
    # patch_rule("update",object="application",object_value=["web-browsing","ssl"],position="pre", rulenames=["all-rules"])
    """
    logger.info ("Running Patch")
    source_hip = ['OCBC-Default-HIP-Profile']
    patch_rule("update",object="source_hip",object_value=source_hip,position="post", rulenames=['Ping test for Gateway'], fix_logging = True, dryrun=dryrun)
    logger.info ("Finish Patch")
    
    # replicate("scm-post-rules-2024-12-18_17-50-24.json", position="post")
    # replicate("test-china.json", position="post")

def replicate(dryrun=True, input_file='input.json', position='post'):
    """
    Replicate SCM json rule
    This only replicate rules that are already exists in the system
    """
    # replicate("scm-post-rules-2024-12-18_17-50-24.json", position="post")
    # replicate("test-china.json", position="post")
    # replicate(input_file, position)


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

    patcher_parser = subparsers.add_parser('patch', help="patch SCM Config")
    patcher_parser.add_argument('-nd',dest='nodryrun',help="Dry Run", action='store_true', default=False)
    
    replicate_parser = subparsers.add_parser('replicate', help="replicate SCM Config")
    replicate_parser.add_argument('-f', '--file', action='store', default='scm-rule.json')
    replicate_parser.add_argument('-p', '--position', choices=['pre','post'], default='post')

    args = parser.parse_args() 

    initialise()

    config_manager = ConfigurationManager(args.config)
    config = config_manager.app_config

    if args.command == 'backup':
        backup(folder=args.folder,format=args.format)

    if args.command == 'patch':
        patch(dryrun=not args.nodryrun)

    if args.command == 'replicate':
        replicate(dryrun=args.dryrun, input_file=args.file, position=args.position)
    
    
    
    


