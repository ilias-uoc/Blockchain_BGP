import re
import pytricia # install as described in https://github.com/jsommers/pytricia


def get_siblings_asns_orgs(input_file = "../CAIDA-asorg2info/20170401.as-org2info.txt"):
    '''
    :param input_file of CAIDA dataset
    :return: siblings of asn, orgs info, asns info
    '''
    orgs = {}
    asns = {}
    org_2_asns = collections.defaultdict(set)
    siblings = {}

    try:
        with open(input_file, 'r') as f:
            read_orgs = False
            read_asns = False

            for line in f.readlines():
                if re.match('# format:org_id|changed|org_name|country|source', line):
                    read_orgs = True
                    read_asns = False
                    continue
                elif re.match('# format:aut|changed|aut_name|org_id|source', line):
                    read_orgs = False
                    read_asns = True
                    continue

                if read_orgs:
                    org_info = line.split('|')
                    orgs[org_info[0]] = {
                        'id'       : org_info[0],
                        'changed'  : org_info[1],
                        'org_name' : org_info[2],
                        'country'  : org_info[3],
                        'source'   : org_info[4].rstrip().lstrip()
                    }

                if read_asns:
                    asn_info = line.split('|')
                    asns[asn_info[0]] = {
                        'asn'       : asn_info[0],
                        'changed'   : asn_info[1],
                        'aut_name'  : asn_info[2],
                        'org_id'    : asn_info[3],
                        'source'    : asn_info[4].rstrip().lstrip()
                    }

                    org_2_asns[asn_info[3]].add(asn_info[0])
    except:
        print("ERROR with processing asn and org data")

    for org_id, asn_set in org_2_asns.items():
        for asn in asn_set:
            siblings[asn] = asn_set.difference(set([asn]))

    return (siblings, orgs, asns)


def get_as_prefs(input_file = "./my_routeviews-rv2-20180328-0000.pfx2as"):
    as2pref     = {}
    pref2as_pyt = pytricia.PyTricia()

    try:
        with open(input_file, 'r') as f:
            for line in f.readlines():
                ipnet_match = re.match('^\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+(\d+)\s+(\S+)$', line)
                if ipnet_match:
                    ipnet    = ipnet_match.group(1)
                    ipmask   = ipnet_match.group(2)
                    asn_list = ipnet_match.group(3).rstrip().lstrip().split('_')

                    prefix              = "%s/%s" % (ipnet, ipmask)
                    pref2as_pyt[prefix] = asn_list

                    for asn in asn_list:
                        if asn not in as2pref:
                            as2pref[asn] = set([])
                        as2pref[asn].add(prefix)
    except:
        print("ERROR with processing asn and prefix data")


    # for json export (sets are not exported)
    for asn in as2pref:
        as2pref[asn] = list(as2pref[asn])

    return (as2pref, pref2as_pyt)
