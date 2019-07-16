## Name: Rohit Joshi
## 11/5/2016
## A script to monitor DNS change for Nginx upstream config and reload nginx
## https://github.com/rohitjoshi/reload-nginx
## python nginx_reloader.py -d -n /opt/nginx/sbin/nginx -c /opt/nginx/conf/upstream.conf --log_file=/tmp/nginx_reloader.log

import time
import dns.resolver #import the module
import subprocess
import argparse
import logging

parser = argparse.ArgumentParser(
    description='A script to monitor DNS change for Nginx upstream config and reload nginx'
)
parser.add_argument(
    '-d', '--debug',
    help='Print lots of debugging statements',
    action='store_const', dest='loglevel', const=logging.DEBUG,
    default=logging.WARNING,
)
parser.add_argument('-s', '--stdout')
parser.add_argument('-n', '--nginx_path', dest='nginx_path',default='/opt/nginx/sbin/nginx')
parser.add_argument('-c', '--upstream_conf', dest='upstream_conf', default='/opt/nginx/conf/upstream.conf')
parser.add_argument('-i', '--include', dest='include_list', default='', help='Comma separated list of servers to only include')
parser.add_argument('-e', '--exclude', dest='exclude_list', default='', help='Comma separated list of servers to only exclude')
parser.add_argument('-t', '--duration', dest='duration', default=60, help='DNS checking interval')
args = parser.parse_args()
logging.basicConfig(filename='logs/nginx-reloader.log', format='%(asctime)s : %(levelname)s : %(message)s', datefmt='%m:%d:%Y %I:%M:%S %p', level=args.loglevel)

# set up logging to console
if args.stdout:
  console = logging.StreamHandler()
  console.setLevel(logging.DEBUG)
  # set a format which is simpler for console use
  formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
  console.setFormatter(formatter)
  # add the handler to the root logger
  logging.getLogger('').addHandler(console)
  logger = logging.getLogger(__name__)

nginx_proc=[args.nginx_path, "-s", "reload"]
nginx_upstream_conf = args.upstream_conf

include_list = args.include_list.split(',')
if include_list == ['']:
  include_list = []

exclude_list = args.exclude_list.split(',')
if exclude_list == ['']:
  exclude_list = []

duration = int(args.duration)

def validate_ip(s):
    a = s.split('.')
    if len(a) != 4:
        return False
    for x in a:
        if not x.isdigit():
            return False
        i = int(x)
        if i < 0 or i > 255:
            return False
    return True

def populate_hosts(fname):
  servers= []
  with open(fname) as f:
    for line in f:
      l = line.strip()
      if l.startswith("server "):
        s = l.split()[1]
        s = s.split(":")[0]
        if not validate_ip(s):
          servers.append(s)
  for server in include_list:
    if server not in servers:
      servers.append(server)
  return servers

def resolve_dns(servers):
  servers_dict = {}
  myResolver = dns.resolver.Resolver() #create a new instance named 'myResolver'
  for server in servers:
    if len(exclude_list) > 0 and server in exclude_list:
      continue
    try:
      myAnswers = myResolver.query(server, "A")
      resolvered_ips = {}
      for rdata in myAnswers:
        logging.debug("resolving server :" + server + " with ip:" + str(rdata))
        resolvered_ips[str(rdata)] = 1
        logging.debug("add server :" + server + " values:" + str(resolvered_ips))

      servers_dict[server] = resolvered_ips
    except Exception as e:
      logging.error("Query failed for server:" + server +  ", Error:" + str(e))
  return servers_dict

def compare_dict(old_dict, new_dict):
  for key in old_dict:
    logging.debug("Checking Host: " + key )
    old_val = old_dict[key]
    if key in new_dict:
      new_val = new_dict[key]
    else:
      logging.warning("DNS Results Changed: Host: " + key + ", not found in new dict")
      return False
    if not new_val or not old_val:
      logging.warning("DNS Results Changed: Host: " + key )
      return False
    if type(new_val) is dict and type(old_val) is dict:
      if not compare_dict(old_val, new_val):
        return False
  return True


def main():
  old_dict = {}
  logging.info("Starting the nginx reloader program...")
  while True:
    try:
      logging.info("#####Loading the nginx upstream file")
      servers = populate_hosts(nginx_upstream_conf)
      logging.info("Resolving hosts")
      new_dict=resolve_dns(servers)
      if not compare_dict(old_dict, new_dict):
        logging.debug("DNS query results changed.")
        logging.warning("reload nginx using command:" + str(nginx_proc) )
        subprocess.call(nginx_proc)
      else:
        logging.debug("DNS query results did not changed")
      old_dict = new_dict
    except Exception as e:
      logging.error("Exception :" + str(e))
    time.sleep( duration )

if __name__ == '__main__':
  main()
